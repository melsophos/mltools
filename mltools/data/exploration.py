"""
Explore data.
"""

import io

import numpy as np
import pandas as pd

import matplotlib.pyplot as plt

from mltools.data import datatools
from mltools.analysis import describe

from mltools.analysis.logger import Logger
from mltools.data.structure import DataStructure


class DataExploration:
    """
    General exploration of a datatset.

    Results can be saved if a logger is given. Since the results of the
    exploration are not expected to change, time is not logged by default
    (contrary to the default parameter of the Logger methods).
    """

    def __init__(self, inputs=None, outputs=None, logger=None):
        # if no inputs, use all columns except the ones in outputs
        # this is done in the `_prepare` method

        if inputs is None:
            self.inputs = []
        else:
            self.inputs = inputs

        if outputs is None:
            self.outputs = []
        else:
            self.outputs = outputs

        self.features = self.inputs + self.outputs

        self.logger = logger

    def _prep_features(self, inputs=None, outputs=None, data=None):

        inputs = inputs or self.inputs
        outputs = outputs or self.outputs

        if isinstance(inputs, str):
            inputs = [inputs]
        if isinstance(outputs, str):
            outputs = [outputs]

        if len(inputs) == 0 and data is not None:
            if isinstance(data, dict):
                inputs = list(data.keys())
            elif isinstance(data, pd.DataFrame):
                inputs = data.columns.to_list()

        if outputs is not None:
            # remove features in `inputs` if they are already in `outputs`
            # this helps in the case where the inputs are infered from the
            # data
            inputs = [f for f in inputs if f not in outputs]

        return inputs, outputs

    def _prep_data(self, data, features):

        if not isinstance(data, (dict, pd.DataFrame)):
            raise TypeError("Data with type `{}` cannot be explored."
                            .format(type(data)))

        if isinstance(data, dict):
            data = datatools.dict_to_dataframe(data)

        data = data[features]

        return data

    def info(self, data, features=None, filename="", logtime=False):

        features, _ = self._prep_features(features, data=data)
        data = self._prep_data(data, features)

        with io.StringIO() as buffer:
            data.info(buf=buffer)
            text = buffer.getvalue()

        if self.logger is not None:
            self.logger.save_text(text, filename, logtime)

        return text

    def describe(self, data, features=None, filename="", logtime=False):

        features, _ = self._prep_features(features, data=data)
        data = self._prep_data(data, features)

        # use include to also describe categories, string (separate display)

        text = str(data.describe(percentiles=[0.1, 0.25, 0.5, 0.75, 0.9]))

        if self.logger is not None:
            self.logger.save_text(text, filename, logtime)

        return text

    def distribution(self, data, features=None, bins=None, figsize=(20, 15),
                     filename="", logtime=False):

        features, _ = self._prep_features(features, data=data)
        data = self._prep_data(data, features)

        bins = bins or min(50, Logger.find_bins(data))

        axes = data.hist(bins=bins, figsize=figsize)

        fig = axes[0, 0].figure

        if self.logger is not None:
            self.logger.save_fig(fig, filename=filename, logtime=logtime)

        plt.close()

        return fig

    def scatter_plots(self, data, inputs=None, outputs=None):

        # data.plot(kind="scatter", x="longitude", y="latitude", alpha=0.1)
        # pd.plotting.scatter_matrix(data)

        pass

    def correlations(self, data, features=None, targets=None,
                     method="pearson", cmap=None, y_rot=45,
                     filename="", logtime=False):
        """
        Compute correlations between a set of features.

        Filename must have no extension.
        """

        features, targets = self._prep_features(features, targets, data=data)
        data = self._prep_data(data, features + targets)

        corr, fig = describe.correlations(data, features, targets, method,
                                          cmap, y_rot, logger=self.logger)
        text = describe.correlation_text(corr)

        # TODO: save as json

        if filename != "" and self.logger is not None:
            self.logger.save_fig(fig, filename + ".pdf'", logtime)
            # self.logger.save_text(text, filename + ".txt", logtime)

        plt.close()

        return corr, fig, text

    def importances(self, data, inputs=None, outputs=None, filename="",
                    logtime=False):
        """
        Compute input importances for outputs from random forest.

        Filename must have no extension.
        """

        importances, fig = describe.importances(data, inputs, outputs)

        # TODO: could make heat map also

        text = ""

        for target, imp in importances.items():
            text += "- {}\n  ".format(target)
            text += describe.importance_text(imp).replace("\n-", "\n  -")
            text += "\n"

        # TODO: save as json

        if filename != "" and self.logger is not None:
            self.logger.save_fig(fig, filename + ".pdf", logtime)
            self.logger.save_text(text, filename + ".txt", logtime)

        return importances, fig, text

    def baseline(self, data, inputs=None, outputs=None, models=None):
        # if model is None, run with simple parameters:
        # linear regression, SVM, basic neural network, random forest

        pass

    def summary_io(self, data, inputs=None, outputs=None, filename="",
                   logtime=False, display_text=False, display_fig=False):

        fulltext = "# Dataset: analysis of inputs and outputs\n\n"
        figs = []

        corr, fig = describe.correlations(data, inputs, outputs)
        text = describe.correlation_text(corr)
        text = "## Correlations between inputs and outputs\n\n" + text

        figs += [fig, Logger.text_to_fig(text)]
        fulltext += text
        fulltext += "\n\n"

        if len(inputs) > 1:
            corr, fig = describe.correlations(data, inputs)
            text = describe.correlation_text(corr)
            text = "## Correlations between inputs\n\n" + text

            figs += [fig, Logger.text_to_fig(text)]
            fulltext += text
            fulltext += "\n\n"

        if len(outputs) > 1:
            corr, fig = describe.correlations(data, outputs)
            text = describe.correlation_text(corr)
            text = "## Correlations between outputs\n\n" + text

            figs += [fig, Logger.text_to_fig(text)]
            fulltext += text
            fulltext += "\n\n"

        _, fig, text = self.importances(data, inputs, outputs)
        text = "## Feature importances (random forests)\n\n" + text

        figs += [fig, Logger.text_to_fig(text)]
        fulltext += text

        if display_text is True:
            print(fulltext)

        if display_fig is True:
            raise NotImplementedError

        if filename != "" and self.logger is not None:
            self.logger.save_figs(figs, filename + ".pdf", logtime)
            self.logger.save_text(fulltext, filename + ".txt", logtime)

    def summary(self, data, features=None, extra_text="", extra_figs=None,
                display_text=False, display_fig=False,
                filename="", logtime=False):

        fulltext = "# Dataset: Exploratory Data Analysis\n\n"
        figs = []

        fulltext += "## Informations\n\n"
        fulltext += self.info(data, features)
        fulltext += "\n\n"

        fulltext += "## Statistics (numerical)\n\n"
        fulltext += self.describe(data, features)
        fulltext += "\n\n\n"

        fig = self.distribution(data, features, figsize=(10, 10))
        figs.append(fig)

        # TODO: take only numerical values
        _, fig, text = self.correlations(data, features)
        figs.append(fig)
        text = "## Correlations\n\n" + text
        figs.append(Logger.text_to_fig(text))
        fulltext += text
        fulltext += "\n"

        fulltext += extra_text

        if extra_figs is not None:
            figs += extra_figs

        if display_text is True:
            print(fulltext)

        if display_fig is True:
            raise NotImplementedError

        if filename != "" and self.logger is not None:
            self.logger.save_figs(figs, filename + ".pdf", logtime)
            self.logger.save_text(fulltext, filename + ".txt", logtime)
