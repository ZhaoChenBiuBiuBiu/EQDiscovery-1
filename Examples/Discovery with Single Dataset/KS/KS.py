# =============================================================================
# Physics-informed learning of governing equations from scarce data
# Zhao Chen, Yang Liu, and Hao Sun
# 2021. Northeastern University

# Main script for the discovery of KS equation with a single dataset 
# =============================================================================

import tensorflow as tf # tensorflow version 1.15.0
import numpy as np
import matplotlib.pyplot as plt
import scipy.io
from scipy.interpolate import griddata
from scipy.spatial import distance
from matplotlib import cm
import time
from mpl_toolkits.mplot3d import Axes3D
from pyDOE import lhs
#    import sobol_seq
import os
from Utils_KS import *

with tf.device('/device:GPU:1'):  # run on GPU

    np.random.seed(1234)
    tf.set_random_seed(1234)
            
# =============================================================================
#     load data
# =============================================================================
    data = scipy.io.loadmat('kuramoto_sivishinky.mat')

    t = np.real(data['t'].flatten()[:,None])
    x = np.real(data['x'].flatten()[:,None])
    Exact = np.real(data['u']).T
    
    X, T = np.meshgrid(x,t)    
    X_star = np.hstack((X.flatten()[:,None], T.flatten()[:,None]))
    u_star = Exact.flatten()[:,None]              

    # Doman bounds
    lb = X_star.min(0)
    ub = X_star.max(0)    

    # Measurement data
    N_u_s = 320 
    idx_s = np.random.choice(x.shape[0], N_u_s, replace=False)
    X0 = X[:, idx_s]
    T0 = T[:, idx_s]
    Exact0 = Exact[:, idx_s]
    
    N_u_t = 101
    idx_t = np.random.choice(t.shape[0], N_u_t, replace=False)
    X0 = X0[idx_t, :]
    T0 = T0[idx_t, :]
    Exact0 = Exact0[idx_t, :]
    
    X_u_meas = np.hstack((X0.flatten()[:,None], T0.flatten()[:,None]))
    u_meas = Exact0.flatten()[:,None]   
    
    # Training measurements
    Split_TrainVal = 0.8
    N_u_train = int(X_u_meas.shape[0]*Split_TrainVal)
    idx_train = np.random.choice(X_u_meas.shape[0], N_u_train, replace=False)
    X_u_train = X_u_meas[idx_train,:]
    u_train = u_meas[idx_train,:]
    
    # Validation Measurements
    idx_val = np.setdiff1d(np.arange(X_u_meas.shape[0]), idx_train, assume_unique=True)
    X_u_val = X_u_meas[idx_val,:]
    u_val = u_meas[idx_val,:]
    
    # Collocation points
    N_f = 30000

    X_f_train = lb + (ub-lb)*lhs(2, N_f)
#    X_f_train = lb + (ub-lb)*sobol_seq.i4_sobol_generate(2, N_f)        
    # X_f_train = np.vstack((X_f_train, X_u_train))
    
    # Optional: Add noise
    noise = 0.1
    u_train = u_train + noise*np.std(u_star)*np.random.randn(u_train.shape[0], u_train.shape[1])
    u_val = u_val + noise*np.std(u_star)*np.random.randn(u_val.shape[0], u_val.shape[1])

# =============================================================================
#   define and train model
# =============================================================================
    layers = [2] + [40]*8 + [1] # 8 hidden layers of 40 nodes

    Adam_epochs_Pre = 80000 
    BFGS_epochs_Pre = 80000 # maximum allowable BFGS epochs in pretraining 
    ADO_iterations = 30
    Adam_epochs_ADO = 100
    BFGS_epochs_ADO = 2000 # maximum allowable BFGS epochs in each ADO iteration 

    # Adam_epochs_Pre = 20 
    # BFGS_epochs_Pre = 20 # maximum allowable BFGS epochs in pretraining 
    # ADO_iterations = 2
    # Adam_epochs_ADO = 20
    # BFGS_epochs_ADO = 20 # maximum allowable BFGS epochs in each ADO iteration 
    
    start_time = time.time()

    model = PiDL(layers, lb, ub, Adam_epochs_Pre, BFGS_epochs_Pre, ADO_iterations, Adam_epochs_ADO, BFGS_epochs_ADO)
    model.train(X_u_train, u_train, X_f_train, X_u_val, u_val)
    
    elapsed = time.time() - start_time                
    print('Training time: %.4f \n' % (elapsed))
# =============================================================================
#   diagnostics
# =============================================================================
    # determine whether the training is sufficient
    model.visualize_training()
    
    u_train_Pred = model.inference(X_u_train)                
    Error_u_Train = np.linalg.norm(u_train-u_train_Pred,2)/np.linalg.norm(u_train,2)   
    print('Training Error u: %e \n' % (Error_u_Train))     
        
    u_val_Pred = model.inference(X_u_val)                
    Error_u_Val = np.linalg.norm(u_val-u_val_Pred,2)/np.linalg.norm(u_val,2)   
    print('Validation Error u: %e \n' % (Error_u_Val))        

# =============================================================================
#   inference the full-field system response (if training is sufficient)
# =============================================================================
    # infer the full-field system response  
    u_FullField_Pred = model.inference(X_star)                
    error_u = np.linalg.norm(u_star-u_FullField_Pred,2)/np.linalg.norm(u_star,2)   
    print('Full Field Error u: %e \n' % (error_u))    

    # visualize the prediction
    U_pred = griddata(X_star, u_FullField_Pred.flatten(), (X, T), method='cubic')
    fig = plt.figure()
    ax = fig.gca(projection='3d')
    surf = ax.plot_surface(X, T, U_pred, cmap=cm.coolwarm,
                       linewidth=0, antialiased=False)    
    ax.set_xlabel('x')
    ax.set_ylabel('t')
    ax.set_zlabel('u')
    plt.title('Model Result')       
    plt.savefig('FullField_ModelPred.png')
    
    fig = plt.figure()
    ax = fig.gca(projection='3d')
    surf = ax.plot_surface(X, T, Exact, cmap=cm.coolwarm,
                       linewidth=0, antialiased=False)
    ax.set_xlabel('x')
    ax.set_ylabel('t')
    ax.set_zlabel('u')
    plt.title('Ground Truth')
    plt.savefig('FullField_GroundTruth.png')
    
    # save inferred system response for plotting manuscript figures in MATLAB.
    scipy.io.savemat('Pred.mat',{'u_FullField_Pred':u_FullField_Pred}) 
    
# =============================================================================
#   compare discovered eq. with the ground truth (if training is sufficient)
# =============================================================================
    lambda_disc = model.sess.run(model.lambda1)
    lambda_true = np.zeros_like(lambda_disc)
    lambda_true[7] = -1 # uu_x
    lambda_true[12] = -1 # u_xx
    lambda_true[24] = -1 # u_xxxx

    nonzero_ind = np.nonzero(lambda_true)
    lambda_error_vector = np.absolute((lambda_true[nonzero_ind]-lambda_disc[nonzero_ind])/lambda_true[nonzero_ind])
    lambda_error_mean = np.mean(lambda_error_vector)*100
    lambda_error_std = np.std(lambda_error_vector)*100
        
    print('lambda_error_mean: %.2f%% \n' % (lambda_error_mean))
    print('lambda_error_std: %.2f%% \n' % (lambda_error_std))
    
    disc_eq_temp = []
    for i_lib in range(len(model.library_description)):
        if lambda_disc[i_lib] != 0:
            disc_eq_temp.append(str(lambda_disc[i_lib,0]) + model.library_description[i_lib])
    disc_eq = '+'.join(disc_eq_temp)        
    print('The discovered equation: u_t = ' + disc_eq)

    # save lambda evolution during training for plotting manuscript figures in MATLAB.
    scipy.io.savemat('LambdaEvolution.mat',{'lambda_history_Pretrain':model.lambda_history_Pretrain[:, 1:],
                                            'lambda_history_STRidge':model.lambda_history_STRidge[:,1:],
                                            'ridge_append_counter_STRidge':model.ridge_append_counter_STRidge[1:]}) 
