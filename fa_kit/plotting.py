"""
Plotting functions for factor analysis
"""
import numpy as np
import matplotlib.pyplot as plt


def graph_summary(fa, num_eigs_to_plot=30):
    """
    Plot a summary of the factor analysis
    """

    has_props = fa.props_raw is not None
    has_raw_comps = fa.comps_raw is not None
    has_rot_comps = fa.comps_rot is not None

    num_panels = has_props + has_raw_comps + has_rot_comps

    fig, axes = plt.subplots(
        figsize=(8, 4 * num_panels),
        ncols=1,
        nrows=num_panels
        )



    if has_props:

        num_eigs_to_plot = np.min([num_eigs_to_plot, len(fa.props_raw)])
        x_range = range(1, num_eigs_to_plot+1)

        p_num = 0

        if fa.retention_opts['method'] == 'top_n':
            axes[p_num].plot(x_range, fa.props_raw[:num_eigs_to_plot], '-ok')
            n = fa.retention_opts['num_keep']
            if n <= num_eigs_to_plot:
                axes[p_num].plot([n, n], axes[p_num].get_ylim(), '--k')
            axes[p_num].set_title(
                'Normed Eigenvalues with top {} cutoff'.format(n))

        elif fa.retention_opts['method'] == 'top_pct':
            vals = np.cumsum(fa.props_raw)
            axes[p_num].plot(x_range, vals[:num_eigs_to_plot], '-ok')
            y = fa.retention_opts['pct_keep']
            axes[p_num].plot(axes[p_num].get_xlim(), [y, y], '--k')

            axes[p_num].set_title('Cumulative Normed Eigenvalues')

        elif fa.retention_opts['method'] == 'kaiser':
            axes[p_num].plot(x_range, fa.props_raw[:num_eigs_to_plot], '-ok')
            y = 1.0 / fa.retention_opts['data_dim']
            axes[p_num].plot(axes[p_num].get_xlim(), [y, y], '--k')
            axes[p_num].set_title(
                'Normed Eigenvalues with Kaiser criterion')

        elif fa.retention_opts['method'] == 'broken_stick':
            axes[p_num].plot(x_range, fa.props_raw[:num_eigs_to_plot], '-ok')
            vals = fa.retention_opts['fit_stick'].values
            axes[p_num].plot(x_range, vals[:num_eigs_to_plot], '--k')
            axes[p_num].set_title(
                'NormedEigenvalues with broken stick superimposed')

        else:
            axes[p_num].set_title('Normed Eigenvalues')

    if has_raw_comps:

        p_num = 1
        axes[p_num].plot(fa.comps_raw[:, fa.retain_idx])
        axes[p_num].set_title('Raw Components')

    if has_rot_comps:

        p_num = 2
        axes[p_num].plot(fa.comps_rot)

        if fa.rotation_opts['method'] == 'varimax':
            axes[p_num].set_title('Varimax Rotated Components')

        elif fa.rotation_opts['method'] == 'quartimax':
            axes[p_num].set_title('Quartimax Rotated Components')
        else:
            axes[p_num].set_title('Rotated Components')

    return fig



def text_summary(fa, top_n_items=10, cutoff=0.5):
    """
    Write out a text summary of what's in each component
    """

    for comp_num, idx in enumerate(fa.retain_idx):

        if fa.comps_rot is not None:
            comp = fa.comps_rot[:, idx]
        elif fa.comps_paf is not None:
            comp = fa.comps_paf[:, idx]
        elif fa.comps_raw is not None:
            comp = fa.comps_raw[:, idx]
        else:
            raise ValueError('No components extracted yet!')

        abs_max = np.abs(comp).max()
        top_n_item_idx = np.argsort(-np.abs(comp))[:top_n_items]
        print('COMPONENT {} (index {})'.format(comp_num, idx))
        for item in top_n_item_idx:
            if np.abs(comp[item]) > (cutoff*abs_max):
                item_score = comp[item]*len(comp)
                item_name = fa.data_opts['labels_dict'][item]
                print("\t{:.1f}: {}".format(item_score, item_name))
            else:
                break
