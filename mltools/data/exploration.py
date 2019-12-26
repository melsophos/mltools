"""
Explore data.
"""

import io

import numpy as np
import pandas as pd

import matplotlib.pyplot as plt


class DataExploration:
    """
    General exploration of a datatset.

    Results can be saved if a logger is given. Since the results of the
    exploration are not expected to change, time is not logged by default
    (contrary to the default parameter of the Logger methods).
    """

    def __init__(self, inputs=None, outputs=None, logger=None):
        # if no inputs, use all columns except the ones in outputs

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

    def _prepare(self, data, features):
        features = features or self.features

        if isinstance(features, str):
            features = [features]

        if features is None or len(features) == 0:
            if isinstance(data, dict):
                features = list(data.keys())
            elif isinstance(data, pd.DataFrame):
                features = list(data.columns)

        if isinstance(data, dict):
            data = pd.DataFrame({k: v for k, v in data.items()
                                 if k in features})
        elif isinstance(data, pd.DataFrame):
            data = data[features]
        else:
            raise TypeError("Data with type `{}` cannot be explored."
                            .format(type(data)))

        return data, features

    def info(self, data, features=None, filename="", logtime=False):
        data, features = self._prepare(data, features)

        buffer = io.StringIO()
        data.info(buf=buffer)

        text = buffer.getvalue()

        if self.logger is not None:
            self.logger.save_text(text, filename, logtime)

        return text

    def describe(self, data, features=None, filename="", logtime=False):
        # use include to also describe categories, string (separate display)

        data, features = self._prepare(data, features)

        data.describe(percentiles=[0.1, 0.25, 0.5, 0.75, 0.9])

        # if self.logger is not None:
        #     self.logger.save_text(text, filename, logtime)

        # return text

    def distribution(self, data, features=None, bins=50, figsize=(20, 15)):
        data, features = self._prepare(data, features)

        data.hist(bins=bins, figsize=figsize)

    @staticmethod
    def _corr_text(corr, xlabels, ylabels=None):

        if ylabels is None:
            ylabels = xlabels

        text = ""
        mat = []

        for x in xlabels:
            c = corr[x][ylabels]
            mat.append(c.values)

            text += "- Correlation: {}\n\n".format(x)
            for k, v in c.sort_values(ascending=False).iteritems():
                text += "{:<25} {:<+.3f}\n".format(k, v)
            text += "\n"

        return text, mat

    @staticmethod
    def _corr_fig(corr, xlabels, ylabels=None):

        if ylabels is None:
            ylabels = xlabels

        axes = plt.matshow(corr, vmin=-1, vmax=1)
        plt.colorbar()

        fig = axes.get_figure()

        # TODO: put ticks below?
        ax = fig.axes[0]

        ax.set_xticks(np.arange(len(xlabels)))
        ax.set_xticklabels(xlabels, rotation=45)

        ax.set_yticks(np.arange(len(ylabels)))
        ax.set_yticklabels(ylabels)

        return fig

    def correlations(self, data, features=None, filename="", logtime=False):
        """
        Compute correlations between a set of features.

        The filename should have no extension.
        """

        data, features = self._prepare(data, features)

        corr = data.corr()

        fig = self._corr_fig(corr, features)
        text, _ = self._corr_text(corr, features)

        if self.logger is not None:
            self.logger.save_fig(fig, filename + ".pdf'", logtime)
            self.logger.save_text(text, filename + ".txt", logtime)

        return text, fig

    def correlations_io(self, data, inputs=None, outputs=None, filename="",
                        logtime=False):
        """
        Compute correlations between inputs and outputs.

        The filename should have no extension.
        """

        features = []

        inputs = inputs or self.inputs
        outputs = outputs or self.outputs

        if len(inputs) == 0 or len(outputs) == 0:
            raise ValueError("Inputs and outputs must be non-empty.")

        data, features = self._prepare(data, inputs + outputs)

        corr = data.corr()

        text, mat = self._corr_text(corr, outputs, inputs)
        fig = self._corr_fig(np.c_[mat].T, outputs, inputs)

        if self.logger is not None:
            self.logger.save_text(text, filename + ".txt", logtime)
            self.logger.save_fig(fig, filename + ".pdf", logtime)

        return text, fig

    def scatter_plots(self, data, inputs=None, outputs=None):

        pass

#        data.plot(kind="scatter", x="longitude", y="latitude", alpha=0.1)
#        pd.plotting.scatter_matrix(data)

    def feature_importance(self, data, inputs=None, outputs=None):
        pass

    def baseline(self, data, inputs=None, outputs=None, models=None):
        # if model is None, run: linear regression, SVM, basic neural network
        # random forest

        pass

    def summary_io(self, data, inputs=None, outputs=None, filename="",
                   logtime=False, display_text=False, display_fig=False):

        inputs = inputs or self.inputs
        outputs = outputs or self.outputs

        fulltext = ""
        figs = []

        text, fig = self.correlations(data, inputs)
        text = "# Correlations between inputs\n\n" + text
        fulltext += text
        figs += [self.logger.text_to_fig(text), fig]

        text, fig = self.correlations(data, outputs)
        text = "# Correlations between outputs\n\n" + text
        fulltext += text
        figs += [self.logger.text_to_fig(text), fig]

        text, fig = self.correlations_io(data, inputs, outputs)
        text = "# Correlations between inputs and outputs\n\n" + text
        fulltext += text
        figs += [self.logger.text_to_fig(text), fig]

        if display_text is True:
            print(fulltext)

        if display_fig is True:
            raise NotImplementedError

        if self.logger is not None:
            self.logger.save_figs(figs, filename + ".pdf", logtime)
            self.logger.save_text(fulltext, filename + ".txt", logtime)

    def summary(self, data, features=None, display_text=False,
                display_fig=False, filename=None):

        text = ""

        text += "# Dataset informations\n"
        text += self.info(data, features)
        text += "\n"

        text += "# Dataset statistics (numerical)"
        text += self.describe(data, features)

        self.distribution(data, features, bins=50, figsize=(10, 10))
        print()

        self.correlations(data, features)
        print()
