#################################
# import functions and packages #
#################################
import os
import argparse
import yaml
import random
import numpy as np
from scipy.special import comb

from Factory import set_problem
from WeightVector import get_weights, determine_neighbor
from Population import init_pop, eval_pop
from ReferencePoint import init_ref_point, update_ref_point
from Mutation import perform_mutation
from Decomposition import agg_value
from PriorityFunctions import priority_values
from AdaptiveStrategy import evolve
from AdaptiveWeightAdjustment import perform_awa, update_EP, init_EP
from SelectMethods import select_solutions
from UpdateMethods import update

###################
# parse arguments #
###################
parser = argparse.ArgumentParser()                                              # read arguments
parser.add_argument('params', type=argparse.FileType('r'))                      # read arguments
parser.add_argument('seed', type=int)                                           # read arguments
args = parser.parse_args()                                                      # read arguments
params = yaml.safe_load(args.params)                                            # read config file

#######################
# define output files #
#######################
save_data = params['save_data']
if save_data == 'True':
    output = params['output']                                                       # set output of record in this run
    os.makedirs(f'./{output}', exist_ok=True)                                       # create a folder to include running results
    os.makedirs(f'./{output}/history/', exist_ok=True)                              # create a folder to include running results
    prefix = params['prob_name']
    os.makedirs(f'./{output}/history/{prefix}_{args.seed}', exist_ok=True)       # create a folder to include running results
    os.makedirs(f'./{output}/final/', exist_ok=True)                                # create a folder to include final results


#########################
# set MOEA/D parameters #
#########################
random.seed(args.seed)                                                          # set the seed for reproducibility purposes
np.random.seed(args.seed)                                                       # set the seed for reproducibility purposes

n_obj = params['n_obj']                                                         # set number of objectives
n_var = params['n_var']                                                         # set number of variables
xl = params['xl']                                                               # set boundary of variables
xu = params['xu']                                                               # set boundary of variables

decomp_method = params['decomp_method']                                            # set decomp method

agg_function = params['agg_function']                                            # set scalar aggregation fuction method

update_name = params['update']                                            # set update method 

n_eval = params['n_eval']                                                       # set maximum number of evaluation

T = params['T']                                                                 # set neighbor size

mutation_list = params['mutation_list']

#######################
# set MOP for solving #
#######################
prob_name = params['prob_name']                                                 # set optimization problem                                               # set optimization problem
problem = set_problem(prob_name, n_var, n_obj, xu, xl)                          # set optimization problem                                               # set optimization problem

###############################
# define MOEA/D configuration #
###############################
W = get_weights(decomp_method, params)

n_pop = len(W)

B = determine_neighbor(W, T)                                                    # determine neighbor

X = init_pop(n_pop, n_var, xl, xu)                                              # initialize a population

Y = eval_pop(X, problem, prob_name)                                                    # evaluate fitness

ref_point = init_ref_point(Y)                                                           # determine a reference point
EP = init_EP(X, Y, n_pop, n_obj)                                                #initialize External population

# P = np.zeros(n_pop) + beta                                                      # generate a set of stability beta parameters 
P = np.random.uniform(params['betal'],params['betau'], n_pop)                                      # generate a set of stability parameters
nr = params['nr']

##################################
# set self adaptive parameters #
##################################
betal = params['betal']                                                         # set lower bound for stability parameter of levy flight mutation
betau = params['betau']                                                         # set upper bound 


alpha_for_param = params['alpha for param']                                     # set scaling factor of levy flight to search parameters
beta_for_param = params['beta for param']                                       # set stability factor of levy flight to search parameters
n_step = params['n_step']                                                       # set number of generations to assess a parameter
P_parent = P[:]                                                                 # initialize a list to store parameters in parent generations
P_offspring = np.full(n_pop, np.nan)                                            # initialize a list to store parameters in offspring generations
I = np.zeros(n_pop)                                                             # initialize a set of indicator vaules
I_parent = I[:]                                                                 # initialize a list to store indicators in parent generations
I_offspring = I[:]                                                              # initialize a list to store indicators in offspring generations

###########################
# set resource allocation #
###########################
priority_function = params['priority_function']                                 # name of the priority function for resource allocation
ps_value = params['ps_value']                                                   # set index parameter of priority functions for resource allocation
priority_values = priority_values(n_pop, priority_function, ps_value)           # generate an array of values for resource allocation based on priority_function named function

################
# start MOEA/D #
################
c_gen = 1                                                                       # control number of generations for output
n_fe = n_pop

while n_fe < n_eval:                                                            # main control loop, how swill the MOEA/D do

    if save_data == 'True':
        result = np.hstack([Y, X])                                                  # record objective values (Y) and decision variables (X)
        np.savetxt(f'./{output}/history/{prob_name}_{args.seed}/{c_gen}_paretos.csv', result)   # record information (Y, X) about the current generation

        info_gen = np.hstack([n_fe, c_gen])                                         # record number of function evaluations and current generation
        np.savetxt(f'./{output}/history/{prob_name}_{args.seed}/{c_gen}_info_gen.csv', info_gen)# record information (n_fe and c_gen) about the current generation

    pv_count = 0
    for i in np.random.permutation(n_pop):                                      # traverse the population; randomly permuting solutions in the population set

        if priority_values[i] >= np.random.uniform():                         # Priority values decide if a solution is candidate for change at an iteration. 
            pv_count += 1                                                                # Solutions canditate for update are the ones with priority values bigger than a random value
            n_fe += 1                                                           # adding 1 to the number of solutions evaluated
            xi_, yi = X[i, :], Y[i, :]                                           # get current individual and its fitness value
            
            j, xj, yj, pool = select_solutions(i, X, Y, B, params)
           
            params['beta'] = P[i]                                                        # self-adaptive beta parameters: set of beta parameters for each subproblem 
            for mutation in mutation_list:
                xi_ = perform_mutation(mutation, xi_, xj, params)             # levy flight mutation
            
            yi_ = problem(xi_)                                              # evaluate offspring (new solution)                                              

            EP = update_EP(EP, np.array([yi_,xi_]), n_pop, n_obj)               # update External population

            ref_point = update_ref_point(ref_point, yi_)                                        # update reference point

            nc = 0                                                              # initialize the update counter
            for k in np.random.permutation(len(pool)):                          # traverse the selection pool

                yk = Y[k, :]                                                    # get k-th individual fitness
                wk = W[k, :]                                                    # get k-th weight vector

                tch_ = agg_value(agg_function, yi_, wk, ref_point)              # compute scalar aggregation value cost of offspring
                tchk = agg_value(agg_function, yk, wk, ref_point)               # compute scalar aggregation value cost of offspring

                nc, X, Y, I = update(update_name, tch_, tchk, nc, X, Y, I)
                if nc >= nr: break

    X, Y, W, B = perform_awa(c_gen, W, X, Y, B, EP, ref_point, params)

    c_gen += 1                                                                   # end of current iteration (generation), add 1

    P, P_parent, P_offspring, I, I_parent, I_offspring = \
        evolve(P, P_parent, P_offspring, I, I_parent, I_offspring,
               B, c_gen, n_step,
               betal, betau, alpha_for_param, beta_for_param)                   # evolve the stability parameters for adaption of levy flight parameters

    
################
# End MOEA/D #
################
if save_data == 'True':
    info_gen = np.hstack([n_fe, c_gen])                                      # record information (n_fe and c_gen) about the current generation
    result = np.hstack([Y, X])                                          # record objective values and decision variables

    np.savetxt(f'./{output}/history/{prob_name}_{args.seed}/{c_gen}_info_gen.csv', info_gen)
    np.savetxt(f'./{output}/history/{prob_name}_{args.seed}/{c_gen}_paretos.csv', result)

    np.savetxt(f'./{output}/final/{prob_name}_{args.seed}_paretos.csv', result)
    np.savetxt(f'./{output}/final/{prob_name}_{args.seed}_info_gen.csv', info_gen)