"""
Define the structure of data

The data is organized in features. Each feature has a specific type (scalar,
tensor, label...).

A tensor type can be represented by its shape. For example, providing the
type `(4, 3, 2)` means that the data is a 3-tensor. The following alias
are used: scalar (0d tensor), vector (1d tensor), matrix (2d tensor). By
default, tensors are considered to have no channels and will be reshaped by
adding a `1` at the end.

The interpretation of the data is not important: the goal of this class is
to convert the data in a form which can be used by the algorithms,
and then back to the original format. The interpretation (converting a
categorical feature to one-hot-encoding, extracting the predictions, etc.)
is done by other classes or functions.

The data structure can present the data according to several modes:
- flat: merged in a single 2d array
- col: by column name
- colflat: by column name of 2d array
"""


import numpy as np
import pandas as pd

import sklearn
from sklearn import preprocessing

import mltools.data.datatools as dt
from mltools.analysis.logger import Logger


# TODO: allow "feature in structure"
# TODO: when transforming, if there is a single feature, can pass
#   single instance (int, etc.) or vec
# TODO: for col mode, can also output list(d.values())
# TODO: use datatypes to specify which labels to group when using
#   multi-label encoding, instead of all possibilities
# TODO: good format for tensorflow
# TODO: for multi-label, write as tuple of features

# transformation modes
_MODES = ['col', 'type', 'flat']

# supported types
_TYPES = ['scalar', 'vector', 'matrix', 'tensor']
# future:  text, image, video, graph

_TENSOR_ALIAS = {'tensor_0d': 'scalar', 'tensor_1d': 'vector',
                 'tensor_2d': 'matrix'}


# TODO: check how to ensure that all tensors have a shape
# TODO: make the DataStructure behave like a list (for loop, in...)


class DataStructure:
    """
    Represent data with conversion

    The goal of this class is to convert data from one format to another,
    performing some automatic conversion depending on the type.

    It is necessary to be explicit about all types (for example tensor shapes)
    because the structure also provides methods to transform back to the
    original format. This is useful for predictions.
    """

    def __init__(self, features=None, datatypes=None, shapes=None,
                 with_channels=None, infer=None,
                 pipeline=None, scaler=None, filter_fn=None, mode='flat',
                 name=''):
        """
        List of features to be transformed. The types can be inferred from
        a dataframe or they can be forced.

        `features` can be a list of features or a dict mapping features
        to types. `datatypes` is a dictionary mapping types to features
        (hence the opposite order). `shapes` is a dict of features mapping
        to a shape used to enforce a specific shape. `with_channels` lists
        all features which have more than one channel.

        Tensors are assumed to have only one channel, except those listed in
        `with_channels`. This means that a tensors will be reshaped to add a
        dimension of size 1 as required by most models.

        The class will determine the types according according to the
        following steps (by increasing priority):
        1. default to scalar with one channel
        2. inference from the argument `infer` (usually a dataframe)
        3. if `features` is a dict, then the values indicated
        4. the key in `datatypes` under which the feature appears

        Similarly, the form of the shapes will be determined according to
        the types, and the sizes of the different dimensions is chosen
        according to (note that there is no default choice):
        1. inference from the argument `infer`
        2. if `features` is a dict, then the values if they are tuples
        3. the values in `shapes`
        In case 1., the biggest shape appearing in a column will be used.

        The `scaler` argument is a dict mapping features to a scaler defined by a `*Scaler` class
        from `sklearn.preprocessing`, or by a custom class having similar properties
        (in particular, with `fit`, `transform` and `inverse_transform` methods). For convenience,
        strings and floats maps standard scalers with default arguments:
        - integer: `ConstantScaler` with parameter given by the float
        - standard: `StandardScaler`
        - minmax: `MinMaxScaler
        - robust: `RobustScaler`

        The class behaves like an iterator for the list `features`.

        :param features: sequence of features or dict of features with datatype
        :type features: list(str), dict(str, str|tuple)
        :param with_channels: sequence of features with channels
        :type with_channels: tuple(str)
        :param infer: data with named features to infer the structure
        :type infer: dataframe, dict(str, array)
        :param name: name of the data structure
        :type name: str
        """

        # TODO: the argument `shapes` is not used

        self.name = name

        if infer is not None:
            if isinstance(infer, dict):
                infer_cols = list(infer.keys())
            elif isinstance(infer, pd.DataFrame):
                infer_cols = list(infer.columns)
            else:
                raise TypeError("Inference works only from an object with "
                                "named features. "
                                "Supported types are: dict, dataframe.")
        else:
            infer_cols = None

        if with_channels is None:
            self.with_channels = []
        else:
            if not isinstance(with_channels, (list, tuple)):
                raise TypeError("`with_channels` must be a list or a tuple, "
                                "{} found.".format(type(with_channels)))

            self.with_channels = with_channels

        self._extract_features_types_shapes(features, datatypes, infer,
                                            infer_cols)

        # default mode
        self.mode = mode

        if mode == 'type':
            raise NotImplementedError

        self.scaler = self.set_scaler(scaler)

        # pass data through scikit pipeline before fit or transformation
        # implemented by the class
        # TODO: consider more general method/function
        self.pipeline = pipeline

        if self.pipeline is not None:
            raise NotImplementedError

    def __contains__(self, key):
        return key in self.features

    def __iter__(self):
        for f in self.features:
            yield f

    def _extract_features_types_shapes(self, features, datatypes, infer,
                                       infer_cols):

        # TODO: make this function independent from class?

        def add_channel_dim(shape, feature):
            shape = tuple(shape)
            return shape if feature in self.with_channels else shape + (1,)

        # list of feature names
        self.features = []
        # map feature to types
        self.types = {}
        # map tensor feature to shape
        self.shapes = {}

        if features is None and datatypes is None:
            # take all columns from `infer` as features if none is given
            self.features += list(infer_cols)
        else:
            if isinstance(features, dict):
                self.features += list(features.keys())
            elif isinstance(features, (list, tuple)):
                self.features += list(features)

            if isinstance(datatypes, dict):
                self.features += list(features.keys())

        # TODO: refactor: for each representation, write special method

        if isinstance(features, dict):
            for f, v in features.items():
                # if the value is a shape, then the type must be a tensor
                if isinstance(v, (tuple, list)):
                    # add trivial channel if necessary
                    shape = add_channel_dim(v, f)
                    self.types[f] = 'tensor_{}d'.format(len(shape) - 1)
                    self.shapes[f] = shape
                elif isinstance(v, str):
                    self.types[f] = v
                    if v == 'scalar':
                        self.shapes[f] = (1,)
                elif v is None:
                    pass
                else:
                    raise ValueError("`{}` type not usable.".format(type(v)))

        # get missing type by looking to the dataset `infer` if defined
        if infer_cols is not None:
            for f in self.features:
                # first element of the data for the feature
                if isinstance(infer, pd.DataFrame):
                    first = infer[f].iloc[0]
                else:
                    first = infer[f][0]

                if isinstance(first, (np.ndarray, list, tuple)):
                    shape = np.shape(first)
                    # TODO: find maximal shape in series

                    shape = add_channel_dim(shape, f)

                # for dataframe only: infer[f].dtype
                if f not in self.types:
                    if (np.issubdtype(type(first), np.integer)
                            or np.issubdtype(type(first), np.floating)):
                        # self.types[f] = 'integer'
                        self.types[f] = 'scalar'
                        self.shapes[f] = (1,)
                    elif isinstance(first, (np.ndarray, list, tuple)):
                        self.types[f] = 'tensor_{}d'.format(len(shape) - 1)
                        self.shapes[f] = shape
                    else:
                        raise TypeError("Type `{}` is not supported."
                                        .format(type(first)))

                # for tensor types defined by features but without the shape
                if (f not in self.shapes
                        and isinstance(first, (np.ndarray, list, tuple))):
                    self.shapes[f] = shape

        # replace tensor types for low dimensions
        for f, t in self.types.items():
            if t in _TENSOR_ALIAS:
                self.types[f] = _TENSOR_ALIAS[t]

        # default type to scalar
        missing_types = {f: "scalar" for f in self.features
                         if f not in self.types}
        self.types.update(missing_types)
        self.shapes.update({f: (1,) for f in missing_types})

        for f in self.features:
            if f not in self.types:
                raise ValueError("The feature `{}` has no type.".format(f))

        for f, t in self.types.items():
            if ((t in ('vector', 'matrix') or t.startswith('tensor'))
                    and f not in self.shapes):
                raise ValueError("The feature `{f}` is a tensor without shape."
                                 .format(f))

    def __repr__(self):
        name = f" ({self.name})" if self.name else ""
        return "<DataStructure{}: {}>".format(name, list(self.features))

    def __call__(self, X, mode=None, scaling=True, trivial_dim=False):

        return self.transform(X, mode, scaling=scaling, trivial_dim=trivial_dim)

    def __len__(self):
        return len(self.features)

    @property
    def linear_shape(self):
        return dt.linear_shape(self.shapes.values(), cum=True)

    def set_scaler(self, scaler=None):
        """
        Set scalers for the data structure.
        """

        if scaler is None:
            return {}

        if not isinstance(scaler, dict):
            # TODO: ignore binary data
            # temporary fix: search for onehot in feature name
            scaler = {f: scaler for f in self.features if "onehot" not in f}

        scaler = {f: self._verify_scaler(s) for f, s in scaler.items()}

        return scaler

    @staticmethod
    def _verify_scaler(scaler):

        if isinstance(scaler, str):
            if scaler == "standard":
                scaler = preprocessing.StandardScaler()
            elif scaler == "robust":
                scaler = preprocessing.RobustScaler()
            elif scaler == "minmax":
                scaler = preprocessing.MinMaxScaler()
            else:
                raise ValueError(f"`{scaler}` not known.")
        elif isinstance(scaler, (float, int)):
            scaler = dt.ConstantScaler(scaler)

        if not isinstance(scaler, sklearn.base.TransformerMixin):
            raise TypeError("`scaler` must be a subclass of `TransformerMixin`.")

        return scaler

    def fit(self, X, y=None, reset=False):
        """
        Fit internal properties of the DataStructure such as scalers.

        Parameter `reset` allows to train from scratch (useful if executing) several time the same
        cell.
        """

        if "train" in X:
            X = X["train"]

        if len(self.scaler) > 0:
            for f, data in self.transform_col(X, scaling=False, flatten=True).items():
                if f in self.scaler:
                    self.scaler[f].fit(data)

        return self

    def data_filter(self, X):
        if isinstance(X, (dict, pd.DataFrame)):
            if isinstance(X, dict):
                X = {k: v for k, v in X.items() if k in self.features}
            elif isinstance(X, pd.DataFrame):
                X = X[self.features]

            return X
        else:
            raise NotImplementedError

    def transform(self, X, mode=None, scaling=True, filtering=True, trivial_dim=False):

        # can disable filtering and scaling

        # TODO: X can be a list of tables, with non-overlapping columns
        # useful if data are stored in different ways (images, etc.)

        if mode == 'type':
            raise NotImplementedError

        mode = mode or self.mode

        if mode == 'flat':
            return self.transform_flat(X, scaling=scaling)
        elif mode == 'col':
            return self.transform_col(X, scaling=scaling, flatten=False, trivial_dim=trivial_dim)
        elif mode == 'colflat':
            return self.transform_col(X, scaling=scaling, flatten=True)
        else:
            raise ValueError("No mode `{}` available.".format(mode))

    def transform_flat(self, X, scaling=False):

        result = []

        for f, data in dt.tab_to_array(self.data_filter(X)).items():
            result.append(self._transform_array(f, data, scaling=scaling, flatten=True))

        return np.hstack(result)

    def _transform_array(self, feature, array, scaling=False, flatten=False):
        """
        Shortcut to transform an array using a scaler.

        The array must be reshaped to 2d before applying the scaler, and then back to its original
        shape.

        Moreover, the method checks whether there is a scaler for the corresponding feature. If
        not, it just returns the array.
        """

        shape = array.shape

        if scaling is True and len(self.scaler) > 0:
            if feature in self.scaler:
                array = self.scaler[feature].transform(array.reshape(shape[0], -1))

        if flatten is True:
            return array.reshape(shape[0], -1)
        else:
            return array

    def transform_col(self, X, scaling=False, flatten=False, trivial_dim=False):
        """
        Transform data to a dict of arrays.

        If `flatten` is true, arrays are all 2d.
        """

        result = {}

        # keep id column
        if isinstance(X, pd.DataFrame):
            # this condition must appear first because next condition also matches the id column
            # in a dataframe but does not convert the index
            result["id"] = X.index.to_numpy()
        elif "id" in X:
            result["id"] = X["id"]

        for f, data in dt.tab_to_array(self.data_filter(X)).items():
            result[f] = self._transform_array(f, data, scaling=scaling, flatten=flatten)

        # TODO: improve this: I think that padding should not be done here
        #       but precise it in the explanations of the class

        # There can be a shape mismatch between what the structure specifies
        # and what the function `tab_to_array` returns since the latter
        # does not know about shape. Since padding must be done before,
        # the only point can be the additional `1` of the last dimension.

        # if `trivial_dim` is True, include the final `1`
        if flatten is False:
            if trivial_dim is True:
                for k, v in result.items():
                    if k != 'id' and v.shape[1:] != self.shapes[k]:
                        result[k] = v.reshape(-1, *self.shapes[k])
            else:
                for k, v in result.items():
                    if k != 'id' and v.shape[-1] == 1:
                        result[k] = v.reshape(*v.shape[:-1])

        return result

    def inverse_transform(self, y, scaling=True, filtering=True):
        if isinstance(y, dict):
            return self.inverse_transform_col(y, scaling=scaling)
        elif isinstance(y, np.ndarray):
            return self.inverse_transform_flat(y, scaling=scaling)
        else:
            raise NotImplementedError

    def inverse_transform_flat(self, y, scaling=False):
        return self.inverse_transform_col(dt.array_to_dict(y, self.shapes), scaling=scaling)

    def inverse_transform_col(self, y, scaling=False):
        dic = {}

        for k, v in y.items():
            shape = v.shape if k in self.with_channels else v.shape[:-1]
            if shape == ():
                shape = (-1,)

            if scaling is True and len(self.scaler) > 0:
                if k in self.scaler:
                    v = self.scaler[k].inverse_transform(v.reshape(shape[0], -1))

            dic[k] = v.reshape(*shape)

        return dic

    def average(self, ensemble):
        """
        Compute average of an ensemble of data.

        Note that the different elements of the ensemble can have different
        features if written as a dict.

        This is a simple average method which does not take into account
        the features.
        """

        # TODO: write second method for more complete average for other types

        return dt.average(ensemble)

    def distance(self, x1, x2, metric=None):
        """
        Compute distance between two datasets using the appropriate metric.
        """

        raise NotImplementedError

    def summary(self, name="", filename="", logtime=False,
                logger=None, show=False, mode='dict'):
        """
        Summary of the data structure.

        The name can be changed using the `name` parameter.
        """

        dic = {}
        text = ""

        if name == "":
            name = self.name or "Features"

        dic = {"name": name, "features": self.features}

        # TODO: add filter infos
        # TODO: add scaling infos

        text += f"{name}:\n"

        text += '\n'.join(f"- {feature}" for feature in self.features)

        if filename != "":
            if logger is None:
                logger = Logger(logtime="filename")

            logger.save_json(dic, filename=filename, logtime=logtime)

        if show is True:
            print(text)

        if mode == 'text':
            return text
        else:
            return dic
