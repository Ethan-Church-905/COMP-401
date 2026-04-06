"""
visualization_and_plots_hc.py :: produces six figures analysing diffusion metrics and cortical
thickness for HC subjects only.

Usage: python visualization_and_plots_hc.py <brain_csv> <tract_csv> <thickness_csv> <profile_dir> <output_dir>
    brain_csv     : CSV from average_brain.py   (columns: subject, fa, md, ad, rd)
    tract_csv     : CSV from average_tract.py   (columns: subject, metric, lh_mean, rh_mean)
    thickness_csv : CSV from cortical_thickness.py (columns: subject, lh_precentral_thickness,
                    rh_precentral_thickness, lh_whole_brain_thickness, rh_whole_brain_thickness)
    profile_dir   : directory containing .pkl files from compute_tract_profile.py
    output_dir    : directory to save figure PNGs
"""

import pickle
import sys
import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats as sp_stats

METRICS = ['fa', 'md', 'ad', 'rd']
METRIC_LABELS = {'fa': 'FA', 'md': 'MD', 'ad': 'AD', 'rd': 'RD'}
GROUP = 'HC'
GROUP_COLOR = 'royalblue'


def _filter_hc(df):
    """Keep only rows whose subject ID starts with 'HC'."""
    return df[df['subject'].str.startswith(GROUP)].copy()


def load_brain_data(brain_csv):
    df = pd.read_csv(brain_csv)
    return _filter_hc(df)


def load_tract_data(tract_csv):
    df = pd.read_csv(tract_csv)
    df = _filter_hc(df)
    df['tract_mean'] = df[['lh_mean', 'rh_mean']].mean(axis=1)
    wide = df.pivot(index='subject', columns='metric', values='tract_mean').reset_index()
    wide.columns.name = None
    wide = wide.rename(columns={m: f'{m}_tract' for m in METRICS})
    return wide


def load_thickness_data(thickness_csv):
    df = pd.read_csv(thickness_csv)
    df = _filter_hc(df)
    df['motor_cortex_thickness'] = df[['lh_precentral_thickness', 'rh_precentral_thickness']].mean(axis=1)
    df['whole_brain_thickness'] = df[['lh_whole_brain_thickness', 'rh_whole_brain_thickness']].mean(axis=1)
    return df


# ---------------------------------------------------------------------------
# Figure 1: 4-panel box plot — HC whole-brain average of each metric
# ---------------------------------------------------------------------------
def plot_brain(brain_df, output_dir):
    fig, axes = plt.subplots(1, 4, figsize=(16, 4))
    for ax, metric in zip(axes, METRICS):
        sns.boxplot(data=brain_df, y=metric, ax=ax, color=GROUP_COLOR)
        ax.set_title(f'Whole-Brain {METRIC_LABELS[metric]}')
        ax.set_ylabel(METRIC_LABELS[metric])
    fig.suptitle('Whole-Brain Diffusion Metrics (HC)', y=1.02)
    fig.tight_layout()
    fig.savefig(os.path.join(output_dir, 'fig1_brain_hc.png'), dpi=300, bbox_inches='tight')
    plt.close(fig)
    print('Saved fig1_brain_hc.png')


# ---------------------------------------------------------------------------
# Figure 2: 4-panel box plot — whole-brain avg vs tract avg for HC
# ---------------------------------------------------------------------------
def plot_brain_vs_tract(brain_df, tract_df, output_dir):
    merged = brain_df.merge(tract_df, on='subject', how='inner')

    fig, axes = plt.subplots(1, 4, figsize=(16, 4))
    for ax, metric in zip(axes, METRICS):
        plot_data = pd.DataFrame({
            'subject': np.tile(merged['subject'].values, 2),
            'region': np.repeat(['Whole Brain', 'Tract'], len(merged)),
            'value': np.concatenate([merged[metric].values,
                                     merged[f'{metric}_tract'].values]),
        })
        sns.boxplot(data=plot_data, x='region', y='value', ax=ax, color=GROUP_COLOR)
        ax.set_title(METRIC_LABELS[metric])
        ax.set_xlabel('')
        ax.set_ylabel(METRIC_LABELS[metric])
    fig.suptitle('Whole-Brain vs Tract Average (HC)', y=1.02)
    fig.tight_layout()
    fig.savefig(os.path.join(output_dir, 'fig2_brain_vs_tract_hc.png'), dpi=300, bbox_inches='tight')
    plt.close(fig)
    print('Saved fig2_brain_vs_tract_hc.png')


# ---------------------------------------------------------------------------
# Figure 3: Box plot — whole-brain vs motor cortex cortical thickness for HC
# ---------------------------------------------------------------------------
def plot_thickness(thickness_df, output_dir):
    plot_data = pd.DataFrame({
        'subject': np.tile(thickness_df['subject'].values, 2),
        'region': np.repeat(['Whole Brain', 'Motor Cortex'], len(thickness_df)),
        'thickness': np.concatenate([thickness_df['whole_brain_thickness'].values,
                                     thickness_df['motor_cortex_thickness'].values]),
    })

    fig, ax = plt.subplots(figsize=(6, 5))
    sns.boxplot(data=plot_data, x='region', y='thickness', ax=ax, color=GROUP_COLOR)
    ax.set_title('Cortical Thickness (HC)')
    ax.set_xlabel('')
    ax.set_ylabel('Cortical Thickness (mm)')
    fig.tight_layout()
    fig.savefig(os.path.join(output_dir, 'fig3_thickness_hc.png'), dpi=300, bbox_inches='tight')
    plt.close(fig)
    print('Saved fig3_thickness_hc.png')


# ---------------------------------------------------------------------------
# Figure 4: 4-panel scatter — tract-average metrics vs motor cortex thickness
# ---------------------------------------------------------------------------
def plot_metric_vs_thickness(tract_df, thickness_df, output_dir):
    merged = tract_df.merge(thickness_df[['subject', 'motor_cortex_thickness']],
                            on='subject', how='inner')

    fig, axes = plt.subplots(1, 4, figsize=(18, 4))
    for ax, metric in zip(axes, METRICS):
        col = f'{metric}_tract'
        x = merged[col].values
        y = merged['motor_cortex_thickness'].values

        ax.scatter(x, y, color=GROUP_COLOR, alpha=0.7, edgecolors='k', linewidths=0.3)

        valid = ~(np.isnan(x) | np.isnan(y))
        if np.sum(valid) > 2:
            slope, intercept, r, p, _ = sp_stats.linregress(x[valid], y[valid])
            x_line = np.linspace(np.nanmin(x), np.nanmax(x), 100)
            ax.plot(x_line, slope * x_line + intercept, 'k--', linewidth=1)
            ax.set_title(f'{METRIC_LABELS[metric]}  (r={r:.2f}, p={p:.3f})')
        else:
            ax.set_title(METRIC_LABELS[metric])

        ax.set_xlabel(f'Tract {METRIC_LABELS[metric]}')
        ax.set_ylabel('Motor Cortex Thickness (mm)')

    fig.suptitle('Tract Diffusion Metrics vs Motor Cortex Thickness (HC)', y=1.02)
    fig.tight_layout()
    fig.savefig(os.path.join(output_dir, 'fig4_metric_vs_thickness_hc.png'), dpi=300, bbox_inches='tight')
    plt.close(fig)
    print('Saved fig4_metric_vs_thickness_hc.png')


# ---------------------------------------------------------------------------
# Figure 5: 4-panel — per-node correlation (r) with motor cortex thickness
# ---------------------------------------------------------------------------
def plot_node_correlation(profile_dir, thickness_df, output_dir):
    fig, axes = plt.subplots(1, 4, figsize=(18, 4))

    hc_subjects_set = set(thickness_df['subject'])

    for ax, metric in zip(axes, METRICS):
        pkl_path = os.path.join(profile_dir, f'{metric}.pkl')
        if not os.path.exists(pkl_path):
            ax.set_title(f'{METRIC_LABELS[metric]} (no data)')
            continue

        with open(pkl_path, 'rb') as f:
            lh_df, rh_df = pickle.load(f)

        common_subjects = sorted(
            set(lh_df.columns) & set(rh_df.columns) & hc_subjects_set
        )
        if len(common_subjects) < 3:
            ax.set_title(f'{METRIC_LABELS[metric]} (too few subjects)')
            continue

        lh_arr = lh_df[common_subjects].values
        rh_arr = rh_df[common_subjects].values
        profile_arr = (lh_arr + rh_arr) / 2.0

        ct_values = thickness_df.set_index('subject').loc[
            common_subjects, 'motor_cortex_thickness'].values.astype(float)

        n_nodes = profile_arr.shape[0]
        r_values = np.full(n_nodes, np.nan)
        for node in range(n_nodes):
            node_vals = profile_arr[node, :]
            valid = ~(np.isnan(node_vals) | np.isnan(ct_values))
            if np.sum(valid) > 2:
                r, _ = sp_stats.pearsonr(node_vals[valid], ct_values[valid])
                r_values[node] = r

        x_pct = np.arange(1, n_nodes + 1)
        ax.plot(x_pct, r_values, color=GROUP_COLOR, linewidth=1.2)
        ax.axhline(0, color='grey', linewidth=0.5, linestyle='--')
        ax.set_xlabel('% Along Tract')
        ax.set_ylabel('r (Pearson)')
        ax.set_title(METRIC_LABELS[metric])
        ax.set_xlim(1, n_nodes)

    fig.suptitle('Node-wise Correlation with Motor Cortex Thickness (HC)', y=1.02)
    fig.tight_layout()
    fig.savefig(os.path.join(output_dir, 'fig5_node_correlation_hc.png'), dpi=300, bbox_inches='tight')
    plt.close(fig)
    print('Saved fig5_node_correlation_hc.png')


# ---------------------------------------------------------------------------
# Figure 6: 4-panel — along-tract profiles with HC group average
#   Faded lines = individual HC subjects, bold line = group mean
# ---------------------------------------------------------------------------
def plot_tract_profiles(profile_dir, thickness_df, output_dir):
    fig, axes = plt.subplots(1, 4, figsize=(18, 4))

    hc_subjects_set = set(thickness_df['subject'])

    for ax, metric in zip(axes, METRICS):
        pkl_path = os.path.join(profile_dir, f'{metric}.pkl')
        if not os.path.exists(pkl_path):
            ax.set_title(f'{METRIC_LABELS[metric]} (no data)')
            continue

        with open(pkl_path, 'rb') as f:
            lh_df, rh_df = pickle.load(f)

        common_subjects = sorted(
            s for s in (set(lh_df.columns) & set(rh_df.columns))
            if s.startswith(GROUP)
        )
        if len(common_subjects) == 0:
            ax.set_title(f'{METRIC_LABELS[metric]} (no subjects)')
            continue

        lh_arr = lh_df[common_subjects].values
        rh_arr = rh_df[common_subjects].values
        profile_arr = (lh_arr + rh_arr) / 2.0
        n_nodes = profile_arr.shape[0]
        x_pct = np.arange(1, n_nodes + 1)

        # Faded individual subject lines
        for si in range(len(common_subjects)):
            ax.plot(x_pct, profile_arr[:, si], color=GROUP_COLOR, alpha=0.15, linewidth=0.6)

        # Bold group-average line
        grp_mean = np.nanmean(profile_arr, axis=1)
        ax.plot(x_pct, grp_mean, color=GROUP_COLOR, linewidth=2.2, label=GROUP)

        ax.set_xlabel('% Along Tract')
        ax.set_ylabel(METRIC_LABELS[metric])
        ax.set_title(METRIC_LABELS[metric])
        ax.set_xlim(1, n_nodes)
        ax.legend(loc='best', fontsize='small')

    fig.suptitle('Along-Tract Profiles (HC)', y=1.02)
    fig.tight_layout()
    fig.savefig(os.path.join(output_dir, 'fig6_tract_profiles_hc.png'), dpi=300, bbox_inches='tight')
    plt.close(fig)
    print('Saved fig6_tract_profiles_hc.png')


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main(brain_csv, tract_csv, thickness_csv, profile_dir, output_dir):
    os.makedirs(output_dir, exist_ok=True)

    brain_df = load_brain_data(brain_csv)
    tract_df = load_tract_data(tract_csv)
    thickness_df = load_thickness_data(thickness_csv)

    plot_brain(brain_df, output_dir)
    plot_brain_vs_tract(brain_df, tract_df, output_dir)
    plot_thickness(thickness_df, output_dir)
    plot_metric_vs_thickness(tract_df, thickness_df, output_dir)
    plot_node_correlation(profile_dir, thickness_df, output_dir)
    plot_tract_profiles(profile_dir, thickness_df, output_dir)


if __name__ == "__main__":
    brain_csv = sys.argv[1]
    tract_csv = sys.argv[2]
    thickness_csv = sys.argv[3]
    profile_dir = sys.argv[4]
    output_dir = sys.argv[5]
    main(brain_csv, tract_csv, thickness_csv, profile_dir, output_dir)
