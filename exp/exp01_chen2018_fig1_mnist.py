"""Experiments performed in Chen et al.: BDA-PCH, figure 1.

Link to the reference:
    https://arxiv.org/pdf/1802.06502v2.pdf
"""

import torch
from torch.nn import CrossEntropyLoss
from torch.optim import SGD
from os import path, makedirs
import matplotlib.pyplot as plt
from .models.chen2018 import original_mnist_model
from .loading.load_mnist import MNISTLoader
from .training.first_order import FirstOrderTraining
from .training.second_order import SecondOrderTraining
from .training.runner import TrainingRunner
from .plotting.plotting import OptimizationPlot
from .utils import (directory_in_data,
                    directory_in_fig,
                    dirname_from_params)
from bpexts.optim.cg_newton import CGNewton


# global hyperparameters
batch = 500
epochs = 20
device = torch.device('cuda:0' if torch.cuda.is_available() else 'cpu')
dirname = 'exp01_reproduce_chen_figures/mnist'
data_dir = directory_in_data(dirname)
fig_dir = directory_in_fig(dirname)
logs_per_epoch = 3


def mnist_sgd_train_fn():
    """Create training instance for MNIST SGD experiment."""
    # hyper parameters
    # ----------------
    lr = 0.1
    momentum = 0.9

    # logging directory
    # -----------------
    # directory of run
    run_name = dirname_from_params(opt='sgd',
                                   batch=batch,
                                   lr=lr,
                                   mom=momentum)
    logdir = path.join(data_dir, run_name)

    # training procedure
    # ------------------
    def training_fn():
        """Training function setting up the train instance."""
        model = original_mnist_model()
        # NOTE: Important line, deactivate extension hooks/buffers!
        model.disable_exts()
        loss_function = CrossEntropyLoss()
        data_loader = MNISTLoader(train_batch_size=batch)
        optimizer = SGD(model.parameters(),
                        lr=lr,
                        momentum=momentum)
        # initialize training
        train = FirstOrderTraining(model,
                                   loss_function,
                                   optimizer,
                                   data_loader,
                                   logdir,
                                   epochs,
                                   logs_per_epoch=logs_per_epoch,
                                   device=device)
        return train
    return training_fn


def mnist_cgnewton_train_fn(modify_2nd_order_terms):
    """Create training instance for MNIST CG experiment.

    Parameters:
    -----------
    modify_2nd_order_terms : (str)
        Strategy for treating 2nd-order effects of module functions:
        * `'zero'`: Yields the Generalizes Gauss Newton matrix
        * `'abs'`: BDA-PCH approximation
        * `'clip'`: Different BDA-PCH approximation
    """
    # hyper parameters
    # ----------------
    lr = 0.1
    alpha = 0.02
    cg_maxiter = 50
    cg_tol = 0.1
    cg_atol = 0

    # logging directory
    # -----------------
    # directory of run
    run_name = dirname_from_params(opt='cgn',
                                   batch=batch,
                                   lr=lr,
                                   alpha=alpha,
                                   maxiter=cg_maxiter,
                                   tol=cg_tol,
                                   atol=cg_atol,
                                   mod2nd=modify_2nd_order_terms)
    logdir = path.join(data_dir, run_name)

    # training procedure
    # ------------------
    def train_fn():
        """Training function setting up the train instance."""
        # set up training and run
        model = original_mnist_model()
        loss_function = CrossEntropyLoss()
        data_loader = MNISTLoader(train_batch_size=batch)
        optimizer = CGNewton(model.parameters(),
                             lr=lr,
                             alpha=alpha,
                             cg_atol=cg_atol,
                             cg_tol=cg_tol,
                             cg_maxiter=cg_maxiter)
        # initialize training
        train = SecondOrderTraining(model,
                                    loss_function,
                                    optimizer,
                                    data_loader,
                                    logdir,
                                    epochs,
                                    modify_2nd_order_terms,
                                    logs_per_epoch=logs_per_epoch,
                                    device=device)
        return train
    return train_fn


if __name__ == '__main__':
    seeds = range(10)
    labels = [
              'SGD',
              'CG (GGN)',
              'CG (PCH, abs)',
              'CG (PCH, clip)',
             ]
    experiments = [
                   # 1) SGD curve
                   mnist_sgd_train_fn(),
                   # 2) Jacobian curve
                   mnist_cgnewton_train_fn('zero'),
                   # 3) BDA-PCH curve
                   mnist_cgnewton_train_fn('abs'),
                   # 4) alternative BDA-PCH curve
                   mnist_cgnewton_train_fn('clip'),
                  ]


    # run experiments
    # ---------------
    metric_to_files = None
    for train_fn in experiments:
        runner = TrainingRunner(train_fn)
        runner.run(seeds)
        m_to_f = runner.merge_runs(seeds)
        if metric_to_files is None:
            metric_to_files = {k : [v] for k, v in m_to_f.items()}
        else:
            for key, value in m_to_f.items():
                metric_to_files[key].append(value)

    # plotting
    # --------
    for metric, files in metric_to_files.items():
        out_file = path.join(fig_dir, metric)
        makedirs(fig_dir, exist_ok=True)
        # figure
        plt.figure()
        plt.legend()
        OptimizationPlot.create_standard_plot('epoch',
                                              metric,
                                              files,
                                              labels,
                                              # scale by training set
                                              scale_steps=60000)
        # fine tuning
        plt.ylim(top=1)
        OptimizationPlot.save_as_tikz(out_file)
