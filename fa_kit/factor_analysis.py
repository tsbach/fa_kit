"""
The FactorAnalysis object that does most of the work
"""


import numpy as np
import pandas as pd

import fa_kit as fa

from fa_kit.broken_stick import BrokenStick


#
# Custom exceptions
#

class NonSquareMatrix(ValueError):
    """
    Exception raised for non-square matrices
    """

    def __init__(self, **kwargs):

        name = kwargs.keys()[0]
        shape = kwargs[name].shape

        message = (
            'The matrix "{name}" was supposed to be square, but instead '
            'we got something with shape {shape}.'
            ).format(
                name=name,
                shape=shape
            )

        super(NonSquareMatrix, self).__init__(message)

class DimensionMismatch(ValueError):
    """
    Exception raised for mismatched dimensions
    """

    def __init__(self, match_dim=1, **kwargs):

        names = kwargs.keys()
        dims = [kwargs[n].shape[match_dim] for n in names]

        message = (
            'The following matrices supposed to all match on '
            'dimension {match_dim}, but instead we see this: {obs_dims}'
            ).format(
                match_dim=match_dim,
                obs_dims=zip(names, dims)
            )

        super(DimensionMismatch, self).__init__(message)


#
# Utility functions
#

def _panda_to_numpy(df_data, labels):
    df_data = df_data.select_dtypes(include=[np.number])
    if labels is not None:
        print('overwriting input labels with column names')
    labels = df_data.columns.tolist()
    np_data = df_data.as_matrix()

    return np_data, labels


def _cleanup_labels(np_data, labels):
    if labels is not None:
        if len(labels) != np_data.shape[1]:
            err_text = (
                'Number of labels, {}, does not match '
                'number of data features, {}'
                ).format(len(labels), np_data.shape[1])

            raise ValueError(err_text)
    else:
        labels = list(range(np_data.shape[1]))

    return labels


class FactorAnalysis(object):
    """
    Base class for objects extract components
    from data
    """


    def __init__(self):

        self.data_covar = None
        self.noise_covar = None

        self.data_opts = {}
        self.retention_opts = {}
        self.rotation_opts = {}

        self.comps_raw = None
        self.comps_paf = None
        self.comps_rot = None

        self.props_raw = None
        self.retain_idx = None


    def load_data(self, data, is_cov=False):
        """
        load data into factor analysis object
        """

        if not isinstance(data, np.ndarray):
            raise TypeError((
                "Input data is not numpy. It's {}".format(type(data))
                ))

        if is_cov:
            if data.shape[0] != data.shape[1]:
                raise NonSquareMatrix(input_data=data)

            self.data_opts['input_mean'] = None
            self.data_opts['input_scale'] = np.sqrt(
                np.diag(data)
                ).reshape(1, -1)

            if self.data_opts['preproc_scale']:
                data /= self.data_opts['input_scale']
                data /= self.data_opts['input_scale'].T

            self.data_covar = data

        else:

            self.data_opts['input_mean'] = np.mean(data, axis=0, keepdims=True)

            if self.data_opts['preproc_demean']:
                data -= self.data_opts['input_mean']

            self.data_opts['input_scale'] = np.sqrt(np.mean(
                data**2, axis=0, keepdims=True))

            if self.data_opts['preproc_scale']:
                data /= self.data_opts['input_scale']

            self.data_covar = data.T.dot(data) / (data.shape[0] - 1)


    @classmethod
    def load_data_samples(cls, input_data, labels=None, **kwargs):
        """
        Load per-sample data as either an n_samples-by-n_feat numpy array
        or a pandas dataframe with samples as rows and features as columns
        
        preproc_demean indicates whether to demean input before calculating
        covar matrix. preproc_scale indicates whether to scale input before
        calculating covar matrix. Turn on both to calculate a correlation. Turn
        on jut demean for covariance.

        labels is a list of strings or ints used to label columns. If you pass
        in a dataframe for input, that'll overwrite any labels you pass in
        """

        fa_obj = cls()

        data = input_data.copy()
        if isinstance(data, pd.core.frame.DataFrame):
            data, labels = _panda_to_numpy(data, labels)

        labels = _cleanup_labels(data, labels)

        fa_obj.data_opts = {
            'preproc_demean': kwargs.get('preproc_demean', False),
            'preproc_scale': kwargs.get('preproc_scale', False),
            'labels': labels,
            'labels_dict': {key: val for key, val in enumerate(labels)},
            }

        fa_obj.load_data(data, is_cov=False)

        return fa_obj

    @classmethod
    def load_data_cov(cls, input_data, labels=None, preproc_scale=False):
        """
        Load data that is already a square association matrix, such as a 
        covariance matrix.

        Input can be an n_samples-by-n_feat numpy array

        labels is a list of strings or ints used to label columns. 

        Note: pandas not allowed here.
        """

        fa_obj = cls()

        data = input_data.copy()
        labels = _cleanup_labels(data, labels)

        fa_obj.data_opts = {
            'preproc_demean': None,
            'preproc_scale': preproc_scale,
            'labels': labels,
            'labels_dict': {key: val for key, val in enumerate(labels)},
            }

        fa_obj.load_data(data, is_cov=True)

        return fa_obj


    def add_noise_cov(self, input_data):
        """
        Load data that is already a square association matrix, such as a 
        covariance matrix, that measures noise.

        Input can be an n_samples-by-n_feat numpy array

        labels is a list of strings or ints used to label columns. 

        Note: pandas not allowed here.
        """

        if not isinstance(input_data, np.ndarray):
            raise TypeError((
                "Input data is not numpy. It's {}".format(type(input_data))
                ))

        if self.data_covar is None:
            raise ValueError("Load data to define self.data_covar first")

        if input_data.shape[0] != input_data.shape[1]:
            raise NonSquareMatrix(input_data=input_data)

        if input_data.shape[0] != self.data_covar.shape[0]:
            raise DimensionMismatch(
                match_dim=1,
                noise_covar=input_data,
                input_data=self.data_covar
                )


    def extract_components(self):
        """
        decompose data into components
        """

        self.comps_raw, self.props_raw = fa.extraction.extract_components(
            self.data_covar,
            self.noise_covar
            )


    def find_comps_to_retain(self, method='broken_stick', **kwargs):
        """
        Find indices of 'good' components
        default behavior is method='broken_stick' which compares to
        a fitted Broken Stick distribution

        other options:

        top_n: retain the n largest components. requires that you
        pass kwarg num_keep, otherwise n is set to 5

        top_pca: retain however many compenent you need to contain
        the top_pca proportion of all mass

        kaiser: retain the components with absolute values exceeding
        1.0 / data dimensionality. Needs data_dim as input param.

        other
        """


        # Set up parameters

        self.retention_opts['method'] = method

        if method == 'top_n':
            self.retention_opts['num_keep'] = kwargs.get('num_keep', 5)
        elif method == 'top_pct':
            self.retention_opts['pct_keep'] = kwargs.get('pct_keep', .90)
        elif method == 'kaiser':
            self.retention_opts['data_dim'] = kwargs.get(
                'data_dim', len(self.props_raw,))
        elif method == 'broken_stick':
            self.retention_opts['fit_stick'] = BrokenStick(self.props_raw)
        else:
            raise Exception(
                "Unknown method for retention, {}".format(method)
                )


        # Run extraction

        if method == 'top_n':
            self.retain_idx = fa.retention.retain_top_n(
                self.props_raw, self.retention_opts['num_keep']
                )

        elif method == 'top_pct':
            self.retain_idx = fa.retention.retain_top_pct(
                self.props_raw, self.retention_opts['pct_keep']
                )

        elif method == 'kaiser':
            self.retain_idx = fa.retention.retain_kaiser(
                self.props_raw, self.retention_opts['data_dim']
                )

        elif method == 'broken_stick':
            self.retain_idx = fa.retention.retain_broken_stick(
                self.props_raw, self.retention_opts['fit_stick']
                )

        return self.retain_idx



    def reextract_using_paf(self):
        """
        Re-extract the components using "principle axis factoring"
        to downwieght contributions from noise variables and get cleaner
        factors
        """

        self.comps_paf = fa.extraction.extract_using_paf(
            self.comps_raw[:, self.retain_idx],
            self.data_covar,
            noise_covar=self.noise_covar,
            verbose=False
            )


    def rotate_components(self, method='varimax'):
        """
        rotate components
        """

        self.rotation_opts['method'] = method

        if method == 'varimax':
            rot_obj = fa.rotation.VarimaxRotator_python()
        elif method == 'varimax_tf':
            rot_obj = fa.rotation.VarimaxRotator_tf()
        elif method == 'quartimax':
            rot_obj = fa.rotation.QuartimaxRotator_python()
        elif method == 'quartimax_tf':
            rot_obj = fa.rotation.QuartimaxRotator_tf()
        else:
            raise Exception(
                "Unknown method for rotation, {}".format(method)
                )

        if self.comps_paf is not None:
            self.comps_rot = rot_obj.rotate(self.comps_paf)
        else:
            self.comps_rot = rot_obj.rotate(self.comps_raw)

    def get_component_scores(self, input_data):
        """
        get component scores on new data
        """


        # Apply preprocessing
        if self.data_opts['preproc_demean']:
            input_data -= self.data_opts['input_mean']

        if self.data_opts['preproc_scale']:
            input_data /= self.data_opts['input_scale']

        # Project data onto components
        if self.comps_rot is not None:
            return input_data.dot(self.comps_rot)

        if self.comps_paf is not None:
            return input_data.dot(self.comps_paf)

        if self.comps_raw is not None:
            return input_data.dot(self.comps_raw)

        raise Exception('No components found in model. Run extraction.')




