import math
from time import time
import torch
import torch.nn.functional as F
from torch import nn, optim
from torch.utils.tensorboard import SummaryWriter
from torch.utils.data import DataLoader, TensorDataset
import numpy as np
import sys
import os
import datetime
from copy import copy, deepcopy
from model import CNN_RNN, RNN
import random
from utils import get_X_Y, build_path
from sklearn.metrics import r2_score
from sklearn.metrics import mean_absolute_error as MAE
import pandas as pd

device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
sys.path.append('./')

METRICS = {'rmse', 'r2', 'corr'}
        
huber_fn = nn.SmoothL1Loss()
best_test = {'rmse': 1e9, 'r2': -1e9, 'corr':-1e9}
best_val = {'rmse': 1e9, 'r2': -1e9, 'corr':-1e9}

# pred, Y assumed to be 2D: [examples x outputs]
def eval(pred, Y, args):
    # Standardize based on mean/std of each output (crop type)
    # if isinstance(Y, Tensor):
    Y = (Y - args.means) / args.stds
    pred = (pred - args.means) / args.stds
    pred, Y = pred.detach().cpu().numpy(), Y.detach().cpu().numpy()
    metric_names = ['rmse', 'r2', 'corr', 'mae', 'mse', 'mape']
    metrics = {metric_name : {} for metric_name in metric_names}

    for idx in range(Y.shape[-1]): # in enumerate(args.output_names):
        output_name = args.output_names[idx]
        not_na = ~np.isnan(Y[:, idx])
        Y_i = Y[not_na, idx]
        pred_i = pred[not_na, idx]
        if Y_i.shape[0] == 0:
            continue

        # RMSE
        metrics['rmse'][output_name] = np.sqrt(np.mean((pred_i-Y_i)**2))
        # R2
        metrics['r2'][output_name] = r2_score(Y_i, pred_i)
        # corr
        if np.all(Y_i == Y_i[0]) or np.all(pred_i == pred_i[0]):  # If all predictions are the same, calculating correlation produces an error, so just set to 0
            metrics['corr'][output_name] = 0
        else:
            metrics['corr'][output_name] = np.corrcoef(Y_i, pred_i)[0, 1]
        # MAE
        metrics['mae'][output_name] = MAE(Y_i, pred_i)
        # MSE
        metrics['mse'][output_name] = np.mean((pred_i-Y_i)**2)
        # MAPE
        metrics['mape'][output_name] = np.mean(np.abs((Y_i - pred_i) / Y_i))

    # For each metric, average over all outputs
    for metric_name in metrics:
        metrics[metric_name]["avg"] = sum(metrics[metric_name].values()) / len(metrics[metric_name])

    return metrics

# pred, Y can be 2D or 3D, but the last dimension is the "output" dimension. We take the average loss across all outputs.
def loss_fn(pred, Y, args, mode="logcosh"):
    loss = 0

    # Standardize based on mean/std of each output (crop type)
    Y = torch.reshape(Y, (-1, Y.shape[-1]))
    pred = torch.reshape(pred, (-1, pred.shape[-1]))
    Y = (Y - args.means) / args.stds
    pred = (pred - args.means) / args.stds

    # Compute loss for each output (crop type)
    for i in range(Y.shape[-1]):
        # Remove rows with NA label
        not_na = ~torch.isnan(Y[:, i])
        Y_i = Y[not_na, i]
        pred_i = pred[not_na, i]
        if Y_i.shape[0] == 0:
            print("Entire column is NaN")
            continue

        if mode == "huber":
            # huber loss
            loss = huber_fn(pred_i, Y_i)
        elif mode == "logcosh":
            # log cosh loss
            err = Y_i - pred_i
            loss += torch.mean(torch.log(torch.cosh(err + 1e-12)))
    loss = loss / Y.shape[-1]
    if np.isnan(loss.item()):
        print("Loss was nan :(")
        print("True", Y)
        print("Predicted", pred)
        exit(1)
 
    return loss


# Note: if this is called with mode "Test", the metrics will be updated IN ALL CASES.
# Only call this with mode "Test" if the validation loss improved for this epoch.
def update_metrics(rmse, r2, corr, mode):
    if mode == "Val":
        if rmse < best_val['rmse']:
            best_val['rmse'] = rmse
            best_val['r2'] = r2
            best_val['corr'] = corr
    elif mode == "Test":
        # if rmse < best_test['rmse']:
        best_test['rmse'] = rmse
        best_test['r2'] = r2
        best_test['corr'] = corr


def train_epoch(args, model, device, train_loader, optimizer, epoch, writer=None):
    print("\n---------------------")
    print("Epoch ", epoch)
    print("---------------------")
    model.train()
    lr = optimizer.param_groups[0]['lr']
    print("lr =", lr)

    tot_loss = 0.
    tot_batch = len(train_loader)
    all_pred = []
    all_Y = []

    for batch_idx, (X, Y, _, _) in enumerate(train_loader): # 397
        X, Y = X.to(device), Y.to(device) # [64, 5, 431] [64, 5]
        optimizer.zero_grad()
        pred = model(X, Y)
        loss = loss_fn(pred[:, :args.length-1, :], Y[:, :args.length-1, :], args) * args.c1 + \
               loss_fn(pred[:, -1, :], Y[:, -1, :], args) * args.c2

        all_pred.append(pred[:, -1, :])
        all_Y.append(Y[:, -1, :])
        metrics_batch = eval(pred[:, -1, :], Y[:, -1, :], args) # [64, 64]
        # tot_rmse += metrics['rmse']['avg']  # TODO - report individual crop values!
        # tot_r2 += metrics['r2']['avg']
        # if not math.isnan(metrics['corr']['avg']):
        #     tot_corr += metrics['corr']['avg']
        # tot_mae += metrics['mae']['avg']
        # tot_mape += metrics['mape']['avg']

        tot_loss += loss.item()
        loss.backward()
        optimizer.step()

        if batch_idx % args.check_freq == 0:
            n_batch = batch_idx+1
            print("### batch ", batch_idx)
            # print("loss: {}\nrmse: {}\t r2: {}\t corr: {}\n mae: {}\t mape: {}".format(
            #     tot_loss/n_batch, tot_rmse/n_batch, tot_r2/n_batch, tot_corr/n_batch, tot_mae/n_batch, tot_mape/n_batch)
            # )
            print("loss: {}\nrmse: {}\t r2: {}\t corr: {}\n mae: {}\t mape: {}".format(
                tot_loss/n_batch, metrics_batch['rmse']['avg'], metrics_batch['r2']['avg'], metrics_batch['corr']['avg'], metrics_batch['mae']['avg'], metrics_batch['mape']['avg'])
            )
        
        cur_step = tot_batch * epoch + batch_idx
        n_batch = batch_idx + 1
        if writer is not None:
            lr = optimizer.param_groups[0]['lr']
            writer.add_scalar("lr", lr, cur_step)
            writer.add_scalar("Train/loss", tot_loss/n_batch, cur_step)
            writer.add_scalar("Train/rmse", metrics_batch['rmse']['avg'], cur_step)
            writer.add_scalar("Train/r2", metrics_batch['r2']['avg'], cur_step)
            writer.add_scalar("Train/corr", metrics_batch['corr']['avg'], cur_step)
            writer.add_scalar("Train/mae", metrics_batch['mae']['avg'], cur_step)
            writer.add_scalar("Train/mape", metrics_batch['mape']['avg'], cur_step)
            # writer.add_scalar("Train/loss", tot_loss/n_batch, cur_step)
            # writer.add_scalar("Train/rmse", tot_rmse/n_batch, cur_step)
            # writer.add_scalar("Train/r2", tot_r2/n_batch, cur_step)
            # writer.add_scalar("Train/corr", tot_corr/n_batch, cur_step)
            # writer.add_scalar("Train/mae", tot_mae/n_batch, cur_step)
            # writer.add_scalar("Train/mape", tot_mape/n_batch, cur_step)

    n_batch = batch_idx+1
    # print("\n###### Overall training metrics")
    # print("loss: {}\nrmse: {}\t r2: {}\t corr: {}\n mae: {}\t mape: {}".format(
    #     tot_loss/n_batch, tot_rmse/n_batch, tot_r2/n_batch, tot_corr/n_batch, tot_mae/n_batch, tot_mape/n_batch)
    # )

    # Calculate stats on all data
    all_pred = torch.cat(all_pred, dim=0)
    all_Y = torch.cat(all_Y, dim=0)
    metrics_all = eval(all_pred, all_Y, args)
    print("\n###### Overall training metrics")
    print("loss: {}\nrmse: {}\t r2: {}\t corr: {}\n mae: {}\t mape: {}".format(
        tot_loss/n_batch, metrics_all['rmse']['avg'], metrics_all['r2']['avg'], metrics_all['corr']['avg'], metrics_all['mae']['avg'], metrics_all['mape']['avg'])
    )

def val_epoch(args, model, device, test_loader, epoch, mode="Val", writer=None):
    print("********************")
    print("Epoch", epoch, mode)
    print("********************")
    model.eval()
    tot_loss = 0.
    result_dfs = []
    all_pred = []
    all_Y = []
    for batch_idx, (X, Y, counties, years) in enumerate(test_loader):
        X, Y, counties, years = X.to(device), Y.to(device), counties.to(device), years.to(device)
        pred = model(X, Y)
        loss = loss_fn(pred[:, :args.length-1, :], Y[:, :args.length-1, :], args) * args.c1 + \
               loss_fn(pred[:, -1, :], Y[:, -1, :], args) * args.c2
        tot_loss += loss.item()
        all_pred.append(pred[:, -1, :])
        all_Y.append(Y[:, -1, :])

        # metrics = eval(pred[:, -1, :], Y[:, -1, :], args)
        # tot_rmse += metrics['rmse']['avg']
        # tot_r2 += metrics['r2']['avg']
        # tot_corr += metrics['corr']['avg']
        # tot_mae += metrics['mae']['avg']
        # tot_mape += metrics['mape']['avg']
        result_df_dict = {"fips": counties.detach().numpy().astype(int).tolist(),
                          "year": years.detach().numpy().astype(int).tolist()}
        for i in range(Y.shape[2]):
            output_name = args.output_names[i]
            result_df_dict["predicted_" + output_name] = pred[:, -1, i].detach().numpy().tolist()
            result_df_dict["true_" + output_name] = Y[:, -1, i].detach().numpy().tolist()
        result_dfs.append(pd.DataFrame(result_df_dict))

    results = pd.concat(result_dfs)

    n_batch = batch_idx+1

    # Calculate stats on all data
    all_pred = torch.cat(all_pred, dim=0)
    all_Y = torch.cat(all_Y, dim=0)
    metrics_all = eval(all_pred, all_Y, args)
    print("loss: {}\nrmse: {}\t r2: {}\t corr: {}\n mae: {}\t mape: {}".format(
        tot_loss/n_batch, metrics_all['rmse']['avg'], metrics_all['r2']['avg'], metrics_all['corr']['avg'], metrics_all['mae']['avg'], metrics_all['mape']['avg'])
    )
    for i, output_name in enumerate(args.output_names):
        print("{} r2: {}".format(output_name, metrics_all['r2'][output_name]))

    # # print("###### Overall Validation metrics")
    # print("loss: {}\nrmse: {}\t r2: {}\t corr: {}\n mae: {}\t mape: {}".format(
    #     tot_loss/n_batch, tot_rmse/n_batch, tot_r2/n_batch, tot_corr/n_batch, tot_mae/n_batch, tot_mape/n_batch)
    # )
    print("********************")
    update_metrics(metrics_all['rmse']['avg'], metrics_all['r2']['avg'], metrics_all['corr']['avg'], mode)

    if writer is not None:
        writer.add_scalar("{}/loss".format(mode), tot_loss/n_batch, epoch)
        writer.add_scalar("{}/rmse".format(mode), metrics_all['rmse']['avg'], epoch)
        writer.add_scalar("{}/r2".format(mode), metrics_all['r2']['avg'], epoch)
        writer.add_scalar("{}/corr".format(mode), metrics_all['corr']['avg'], epoch)
        writer.add_scalar("{}/mae".format(mode), metrics_all['mae']['avg'], epoch)
        writer.add_scalar("{}/mape".format(mode), metrics_all['mape']['avg'], epoch)

    return metrics_all['rmse']['avg'], results

def train(args):
    print('reading npy...')
    np.random.seed(args.seed) # set the random seed of numpy
    torch.manual_seed(args.seed)

    # TODO this changed!
    print(args.data_dir)
    if args.data_dir.endswith(".npz"):
        raw_data = np.load(args.data_dir) #load data from the data_dir
        data = raw_data['data']
        args.output_names = ["soybean"]
    elif args.data_dir.endswith(".npy"):
        data = np.load(args.data_dir)  #, dtype=float, delimiter=',')
        args.output_names = ["corn", "cotton", "sorghum", "soybeans", "spring_wheat", "winter_wheat"]
        print("Data shape", data.shape)    
    elif args.data_dir.endswith(".csv"):
        data = np.genfromtxt(args.data_dir, dtype=float, delimiter=',')
        args.output_names = ["corn", "cotton", "sorghum", "soybeans", "spring_wheat", "winter_wheat"]
        print("Data shape", data.shape)
    else:
        raise ValueError("--data_dir argument must end in .npz, .npy, or .csv")

    # data = np.load(args.data_dir) #load data from the data_dir

    X_train, Y_train, counties_train, years_train, X_val, Y_val, counties_val, years_val, X_test, Y_test, counties_test, years_test = get_X_Y(data, args)

    # Compute average of each output
    means = []
    stds = []
    for i in range(Y_train.shape[2]):
        Y_i = Y_train[:, -1, i]
        Y_i = Y_i[~np.isnan(Y_i)]
        means.append(np.mean(Y_i))
        stds.append(np.std(Y_i))
    args.means = torch.tensor(means)
    args.stds = torch.tensor(stds)


    # Create Tensors, datasets, dataloaders
    X_train, X_val, X_test = torch.Tensor(X_train), torch.Tensor(X_val), torch.Tensor(X_test)
    Y_train, Y_val, Y_test = torch.Tensor(Y_train), torch.Tensor(Y_val), torch.Tensor(Y_test)
    counties_train, counties_val, counties_test = torch.Tensor(counties_train), torch.Tensor(counties_val), torch.Tensor(counties_test)
    years_train, years_val, years_test = torch.Tensor(years_train), torch.Tensor(years_val), torch.Tensor(years_test)
    print("train:", X_train.shape, Y_train.shape, counties_train.shape, years_train.shape)
    print("val:", X_val.shape, Y_val.shape)
    print("test:", X_test.shape, Y_test.shape)

    train_dataset = TensorDataset(X_train, Y_train, counties_train, years_train)
    train_loader = DataLoader(train_dataset, batch_size=args.batch_size, shuffle=True, num_workers=1)
    val_dataset = TensorDataset(X_val, Y_val, counties_val, years_val)
    val_loader = DataLoader(val_dataset, batch_size=args.batch_size, shuffle=True, num_workers=1)
    test_dataset = TensorDataset(X_test, Y_test, counties_test, years_test)
    test_loader = DataLoader(test_dataset, batch_size=args.batch_size, shuffle=True, num_workers=1)

    n_train = len(X_train)
    param_setting = "{}_bs-{}_lr-{}_maxepoch-{}_sche-{}_T0-{}_testyear-{}_len-{}_seed-{}".format(
        args.model, args.batch_size, args.learning_rate, args.max_epoch, args.scheduler, args.T0, args.test_year, args.length, args.seed)

    summary_dir = 'summary/{}/{}'.format(args.dataset, param_setting)
    model_dir = 'model/{}/{}'.format(args.dataset, param_setting)
    build_path(summary_dir)
    build_path(model_dir)
    writer = SummaryWriter(log_dir=summary_dir)

    print('building network...')

    #building the model 
    if args.model == "cnn_rnn":
        model = CNN_RNN(args).to(device)
    elif args.model == "rnn":
        model = RNN(args).to(device)
    else:
        raise ValueError("model type not supported yet")
    
    #log the learning rate 
    #writer.add_scalar('learning_rate', args.learning_rate)

    #use the Adam optimizer 
    optimizer = optim.Adam(model.parameters(), lr=args.learning_rate, weight_decay=1e-5)
    if args.scheduler == "step":
        scheduler = torch.optim.lr_scheduler.StepLR(optimizer, args.max_epoch//4, 0.5)
    else:
        raise ValueError("scheduler not supported yet")

    '''if args.resume:
        vae.load_state_dict(torch.load(args.checkpoint_path))
        current_step = int(args.checkpoint_path.split('/')[-1].split('-')[-1]) 
        print("loaded model: %s" % args.label_checkpoint_path)
    else:
        current_step = 0'''


    best_val_rmse = 1e9
    for epoch in range(args.max_epoch):
        train_epoch(args, model, device, train_loader, optimizer, epoch, writer)
        val_rmse, val_results = val_epoch(args, model, device, val_loader, epoch, "Val", writer)
        if val_rmse < best_val_rmse:
            val_epoch(args, model, device, test_loader, epoch, "Test", writer)
            best_val_rmse = val_rmse
            torch.save(model.state_dict(), model_dir+'/model-'+str(epoch))
            print('save model to', model_dir)
            print('results file', os.path.join(model_dir, "results.csv"))
            val_results.to_csv(os.path.join(model_dir, "results.csv"), index=False)

        print("BEST Val | rmse: {}, r2: {}, corr: {}".format(best_val['rmse'], best_val['r2'], best_val['corr']))
        print("BEST Test | rmse: {}, r2: {}, corr: {}".format(best_test['rmse'], best_test['r2'], best_test['corr']))
        scheduler.step()
    
