#!/usr/bin/env python

import os
import numpy as np
from simcosinor.cynumstats import cy_lin_lstsqr_mat_residual, cy_lin_lstsqr_mat, se_of_slope
from scipy.stats import t, f, norm
from matplotlib import pyplot as plt
from matplotlib.ticker import StrMethodFormatter
import matplotlib.patches as mpatches


class CosinorExamples:
	modality1_subjects_normed = "%s/simcosinor/examples/examples_subjects_norm_modality_1.csv" % os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
	modality2_subjects_normed = "%s/simcosinor/examples/examples_subjects_norm_modality_2.csv" % os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
	modality3_subjects_normed = "%s/simcosinor/examples/examples_subjects_norm_modality_3.csv" % os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
	modality4_subjects_normed = "%s/simcosinor/examples/examples_subjects_norm_modality_4.csv" % os.path.dirname(os.path.dirname(os.path.realpath(__file__)))

def run_cosinor_simulation(endog, time_variable, period = [24.0], resids = None, randomise_time = False, resample_eveningly = False, n_sampling = None, range_sampling = None, i = 0):

	"""
	Cosinor simulations. The MESOR, amplitude, and acrophase are determined from real data. Simulated data are calculated by adding random gaussian noise to the projected cosinor model. For estimationg of the noise, the residuals from cosinor model are used to determine the mean, and standard deviation. 
	
	Parameters
	----------
	endog : array
		Endogenous (dependent) variable array of real data.
	time_variable : array
		Time points.
	period : array
		The period(s) of the cosinor model
	resids : array
		[optional] input precomputed residuals. Otherwise, it is calculated.
	randomise_time : bool
		Randomise the time points for the simulation within the sample range.
	resample_eveningly : bool
		The time points will be equally distributed across the sample range.
	n_sampling : int
		The number of time points to simulate
	range_sampling: array
		The time range for simulating [start, stop]
	i : int
		Iterator for parallel processing.
	Returns
	---------
	sim_R2 : float
		R-squared of the simulated model
	sim_Fmodel : float
		F-value of the simulated model
	sim_tAMPLITUDE : float
		The amplitude T-value(s) of the simulated model
	ACROPHASE_24 : float
		The acrophase of the simulated model converted to 24H from radians
	p_values
		The simulated model p-value
	"""

	n = len(endog)
	k = len(period)*2 + 1
	DF_Between = k - 1 # aka df model
	DF_Within = n - k # aka df residuals

	# Check that endog has two dimensions
	if endog.ndim == 1:
		endog = endog.reshape(len(endog),1)

	# calculate residuals from cosinor model if not already provided
	if resids is None:
		resids = residual_cosinor(endog = endog, time_var = time_variable, period = period)

	# Calculate true Mesor, Amplitude, Acrophase
	MESOR, AMPLITUDE, ACROPHASE = glm_cosinor(endog = endog, 
															time_var = time_variable,
															period = period,
															calc_MESOR = True,
															output_fit_only = True)

	if randomise_time:
		if n_sampling is None:
			n_sampling = n
		if range_sampling is None:
			range_sampling = [0,23.99]
		if resample_eveningly:
			time_variable = np.linspace(range_sampling[0],range_sampling[1],n_sampling)
		else:
			time_variable = np.sort(np.random.uniform(low=range_sampling[0], high=range_sampling[1], size=(n_sampling,)))
	else:
		n_sampling = n

	# the mean and std of for the noise is calculated from the residuals
	noise_mean = resids.mean()
	noise_std = resids.std()
	noise_npts = n_sampling
	noise = np.random.normal(noise_mean, noise_std, noise_npts).reshape(noise_npts,1)

	# calculate the predicted cosinor curve
	predicted = project_cosionor_model(MESOR, AMPLITUDE, ACROPHASE, TIME_VAR = time_variable, PERIOD = period)
	sim_endog = noise + predicted
	sim_R2, sim_MESOR, _, sim_AMPLITUDE, sim_SE_AMPLITUDE, sim_ACROPHASE, sim_SE_ACROPHASE, sim_Fmodel, _, sim_tAMPLITUDE, _, _ = glm_cosinor(endog = sim_endog, 
																time_var = time_variable,
																period = period,
																calc_MESOR = True,
																output_fit_only = False)

	ACROPHASE_24 = np.zeros_like(sim_ACROPHASE)
	for j, per in enumerate(period):
		acrotemp = np.abs(sim_ACROPHASE[j]/(2*np.pi)) * per
		acrotemp[acrotemp>per] -= per
		ACROPHASE_24[j] = acrotemp

	p_values = f.sf(sim_Fmodel, DF_Between, DF_Within)
	return(sim_R2.squeeze(), sim_Fmodel.squeeze(), sim_tAMPLITUDE.squeeze(), ACROPHASE_24.squeeze(), p_values.squeeze())


def regression_f_ratio(endog, exog_m1, exog_m2, covars = None):
	"""
	Compares regression models
	
	Parameters
	----------
	endog : array
		Endogenous (dependent) variable array (Nsubjects, Nvariables)
	exog_m1 : array
		Exogenous (independent) dummy coded variables
		exog is an array of arrays (Nvariables, Nsubjects)
	exog_m2 : array
		Exogenous (independent) dummy coded variables
		exog is an array of arrays (Nvariables, Nsubjects)
	covars : array
		Dummy coded array of covariates of no interest
	
	Returns
	---------
	F_ratio : array
		F distribution with dof (dfN, dfF)
	"""

	n = endog.shape[0]
	# model1
	k_m1 = exog_m1.shape[1]
	DF_Between_m1 = k_m1 - 1 # aka df model
	DF_Within_m1 = n - k_m1 # aka df residuals
	_, SS_Residuals_m1 = cy_lin_lstsqr_mat_residual(exog_m1,endog)

	k_m2 = exog_m2.shape[1]
	DF_Between_m2 = k_m2 - 1 # aka df model
	DF_Within_m2 = n - k_m2 # aka df residuals
	_, SS_Residuals_m2 = cy_lin_lstsqr_mat_residual(exog_m2,endog)

	# Just to make things easier
	dfN = DF_Within_m2 - DF_Within_m1
	dfF = DF_Within_m1
	dfR = DF_Within_m2

	F_ratio = (((SS_Residuals_m2 - SS_Residuals_m1)/(dfR - dfF))/(SS_Residuals_m1/dfF))
	p_values = f.sf(F_ratio, dfN, dfF)
	return(F_ratio, p_values)


# https://www.ncbi.nlm.nih.gov/pmc/articles/PMC3991883/
# https://www.ncbi.nlm.nih.gov/pmc/articles/PMC3663600/
def glm_cosinor(endog, time_var, exog = None, dmy_covariates = None, rand_array = None, interaction_var = None, period = [24.0], calc_MESOR = True, output_fit_only = False):
	"""
	COSINOR model using GLM
	
	Parameters
	----------
	endog : array
		Endogenous (dependent) variable array (Nsubjects, Nvariables)
	time_var : array
		Time variable [0-23.99] (Nsubjects).
	exog : array
		Exogenous (independent) dummy coded variables
		exog is an array of arrays (Nvariables, Nsubjects, Kvariable).
	dmy_covariates : array
		Dummy coded array of covariates of no interest.
	init_covars : array
		Dummy coded array of covariates for two-step regression.
	rand_array : array
		randomized array for permutations (Nsubjects).
	period : array
		Period(s) as an array of floats for cosinor model.
	Returns
	---------
	To-do
	"""

	n = endog.shape[0]
	# add cosinor terms
	num_period = len(period)
	exog_vars = np.ones((n))
	for i in range(num_period):
		exog_vars = np.column_stack((exog_vars,np.cos(np.divide(2.0*np.pi*time_var, period[i]))))
		exog_vars = np.column_stack((exog_vars,np.sin(np.divide(2.0*np.pi*time_var, period[i]))))

	if interaction_var is not None:
		for i in range(num_period):
			exog_vars = np.column_stack((exog_vars, exog_vars[i+1] * interaction_var))


	kvars = []
	# add other exogenous variables to the model (currently not implemented)
	if exog is not None:
		for var in exog:
			var = np.array(var)
			if var.ndim == 1:
				kvars.append((3))
			else:
				kvars.append((var.shape[1]))
			exog_vars = np.column_stack((exog_vars,var))

	# add covariates (i.e., exogenous variables that will not be outputed)
	if dmy_covariates is not None:
		exog_vars = np.column_stack((exog_vars, dmy_covariates))
	exog_vars = np.array(exog_vars)

	if rand_array is not None:
		exog_vars = exog_vars[rand_array]

	# calculate model fit (Fmodel and R-sqr)
	k = exog_vars.shape[1]
	DF_Between = k - 1 # aka df model
	DF_Within = n - k # aka df residuals
	#DF_Total = n - 1

	a, SS_Residuals = cy_lin_lstsqr_mat_residual(exog_vars,endog)
	if output_fit_only:
		AMPLITUDE = []
		ACROPHASE = []
		MESOR = a[0]
		for i in range(num_period):
			# beta, gamma
			AMPLITUDE.append(np.sqrt((a[1+(i*2),:]**2) + (a[2+(i*2),:]**2)))
			# Acrophase calculation
			if i == 0: # awful hack
				ACROPHASE = np.arctan(np.abs(np.divide(-a[2+(i*2),:], a[1+(i*2),:])))
				ACROPHASE = ACROPHASE[np.newaxis,:]
			else:
				temp_acro = np.arctan(np.abs(np.divide(-a[2+(i*2),:], a[1+(i*2),:])))
				temp_acro = temp_acro[np.newaxis,:]
				ACROPHASE = np.append(ACROPHASE,temp_acro, axis=0)
			ACROPHASE = np.array(ACROPHASE)
			ACROPHASE[i, (a[2+(i*2),:] > 0) & (a[1+(i*2),:] >= 0)] = -ACROPHASE[i, (a[2+(i*2),:] > 0) & (a[1+(i*2),:] >= 0)]
			ACROPHASE[i, (a[2+(i*2),:] > 0) & (a[1+(i*2),:] < 0)] = (-1*np.pi) + ACROPHASE[i, (a[2+(i*2),:] > 0) & (a[1+(i*2),:] < 0)]
			ACROPHASE[i, (a[2+(i*2),:] < 0) & (a[1+(i*2),:] <= 0)] = (-1*np.pi) - ACROPHASE[i, (a[2+(i*2),:] < 0) & (a[1+(i*2),:] <= 0)]
			ACROPHASE[i, (a[2+(i*2),:] <= 0) & (a[1+(i*2),:] > 0)] = (-2*np.pi) + ACROPHASE[i, (a[2+(i*2),:] <= 0) & (a[1+(i*2),:] > 0)]
		return MESOR, np.array(AMPLITUDE), np.array(ACROPHASE)
	else:
		SS_Total = np.sum((endog - np.mean(endog,0))**2,0)
		SS_Between = SS_Total - SS_Residuals
		MS_Residuals = (SS_Residuals / DF_Within)
		Fmodel = (SS_Between/DF_Between) / MS_Residuals
		# Calculates sigma sqr and T-value (intercept) for MESOR
		sigma = np.sqrt(SS_Residuals / DF_Within)
		invXX = np.linalg.inv(np.dot(exog_vars.T, exog_vars))

		if (calc_MESOR) or (exog is not None):
			if endog.ndim == 1:
				se = np.sqrt(np.diag(sigma * sigma * invXX))
				Tvalues = a / se
				MESOR = a[0]
				tMESOR = Tvalues[0]
				SE_MESOR = se[0]
				a = a[:, np.newaxis]
			else:
				num_depv = endog.shape[1]
				se = se_of_slope(num_depv,invXX,sigma**2,k)
				Tvalues = a / se
				MESOR = a[0,:]
				tMESOR = Tvalues[0,:]
				SE_MESOR = se[0,:]
			if exog is not None:
				tEXOG = Tvalues[(3+(2*(num_period-1))):,:]
			else:
				tEXOG = None
		else:
			MESOR = tMESOR = SE_MESOR = tEXOG = None

		AMPLITUDE = []
		ACROPHASE = []
		SE_ACROPHASE = []
		SE_AMPLITUDE = []
		tAMPLITUDE = []
		tACROPHASE = []
		
		for i in range(num_period):
			# beta, gamma
			AMPLITUDE.append(np.sqrt((a[1+(i*2),:]**2) + (a[2+(i*2),:]**2)))
			# Acrophase calculation
			if i == 0: # awful hack
				ACROPHASE = np.arctan(np.abs(np.divide(-a[2+(i*2),:], a[1+(i*2),:])))
				ACROPHASE = ACROPHASE[np.newaxis,:]
			else:
				temp_acro = np.arctan(np.abs(np.divide(-a[2+(i*2),:], a[1+(i*2),:])))
				temp_acro = temp_acro[np.newaxis,:]
				ACROPHASE = np.append(ACROPHASE,temp_acro, axis=0)

			# standard errors from error propagation
			SE_ACROPHASE.append(sigma * np.sqrt((invXX[(1+(i*2)),1+(i*2)]*np.sin(ACROPHASE[i])**2) + (2*invXX[1+(i*2),2+(i*2)]*np.sin(ACROPHASE[i])*np.cos(ACROPHASE[i])) + (invXX[2+(i*2),2+(i*2)]*np.cos(ACROPHASE[i])**2)) / AMPLITUDE[i])
			SE_AMPLITUDE.append(sigma * np.sqrt((invXX[(1+(i*2)),1+(i*2)]*np.cos(ACROPHASE[i])**2) - (2*invXX[1+(i*2),2+(i*2)]*np.sin(ACROPHASE[i])*np.cos(ACROPHASE[i])) + (invXX[2+(i*2),2+(i*2)]*np.sin(ACROPHASE[i])**2)))

			ACROPHASE = np.array(ACROPHASE)
			if rand_array is None:
				ACROPHASE[i, (a[2+(i*2),:] > 0) & (a[1+(i*2),:] >= 0)] = -ACROPHASE[i, (a[2+(i*2),:] > 0) & (a[1+(i*2),:] >= 0)]
				ACROPHASE[i, (a[2+(i*2),:] > 0) & (a[1+(i*2),:] < 0)] = (-1*np.pi) + ACROPHASE[i, (a[2+(i*2),:] > 0) & (a[1+(i*2),:] < 0)]
				ACROPHASE[i, (a[2+(i*2),:] < 0) & (a[1+(i*2),:] <= 0)] = (-1*np.pi) - ACROPHASE[i, (a[2+(i*2),:] < 0) & (a[1+(i*2),:] <= 0)]
				ACROPHASE[i, (a[2+(i*2),:] <= 0) & (a[1+(i*2),:] > 0)] = (-2*np.pi) + ACROPHASE[i, (a[2+(i*2),:] <= 0) & (a[1+(i*2),:] > 0)]
			# t values
			tAMPLITUDE.append(np.divide(AMPLITUDE[i], SE_AMPLITUDE[i]))
			tACROPHASE.append(np.divide(1.0, SE_ACROPHASE[i]))

		# Do not output R-squared during permutations testing.
		R2 = 1 - (SS_Residuals/SS_Total)

		return R2, MESOR, SE_MESOR, np.array(AMPLITUDE), np.array(SE_AMPLITUDE), np.array(ACROPHASE), np.array(SE_ACROPHASE), Fmodel, tMESOR, np.abs(tAMPLITUDE), np.abs(tACROPHASE), np.array(tEXOG)


def permute_cosinor(endog, time_variable, period, iterator, perm_stat = 'Fmodel', blocking = None):
	# Check that endog has two dimensions
	if endog.ndim == 1:
		endog = endog.reshape(len(endog),1)
	if perm_stat == 'Fmodel':
		stat_choice = 7
	else:
		stat_choice = 0
	rand_array = np.random.permutation(list(range(len(time_variable))))
	perm_stat = glm_cosinor(endog = endog,
							time_var = time_variable,
							rand_array = rand_array,
							period = period)[stat_choice]
	return(perm_stat)

def plot_permuted_model(endog, time_variable, period = [24.0], n_perm = 10000, outname = 'cosinor_plot_permuted.png'):
	if endog.ndim == 1:
		endog = endog.reshape(len(endog),1)
	resids = residual_cosinor(endog = endog, time_var = time_variable, period = period)
	Fperm = np.array([permute_cosinor(endog = resids, time_variable = time_variable, period = period, iterator = i) for i in range(n_perm)])
	n = len(time_variable)
	k = len(period)*2 + 1
	DF_Between = k - 1 # aka df model
	DF_Within = n - k # aka df residuals


	R2, MESOR, SE_MESOR, AMPLITUDE, SE_AMPLITUDE, ACROPHASE, SE_ACROPHASE, Fmodel = glm_cosinor(endog = endog, 
								time_var = time_variable,
								period = period,
								calc_MESOR = True,
								output_fit_only = False)[:8]

	model_line, times = create_cosinor_fit(period, 
														MESOR[0],
														AMPLITUDE,
														ACROPHASE,
														time_space = np.linspace(0,24,200))
	plt.figure(figsize=(12,8))
	plt.subplot(2, 1, 1)
	plt.title("Plot of the Cosinor Model")
	plt.plot(times, model_line, c='k')
	plt.scatter(time_variable, endog, marker = '.')
	plt.fill_between(times, model_line - np.mean(np.squeeze(SE_AMPLITUDE)), model_line + np.mean(np.squeeze(SE_AMPLITUDE)), alpha=0.2, color='k')
	# Mesor
	plt.axhline(y=MESOR[0], color='k', alpha = 0.2)
	plt.axhline(y=(MESOR[0] - np.squeeze(SE_MESOR)), color='k', ls=':', alpha = 0.2)
	plt.axhline(y=(MESOR[0] + np.squeeze(SE_MESOR)), color='k', ls=':', alpha = 0.2)

	ACROPHASE_24 = np.zeros_like(ACROPHASE)
	for j, per in enumerate(period):
		acrotemp = np.abs(ACROPHASE[j]/(2*np.pi)) * per
		acrotemp[acrotemp>per] -= per
		ACROPHASE_24[j] = acrotemp
	ACROPHASE_SE_24 = np.zeros_like(SE_ACROPHASE)
	for j, per in enumerate(period):
		acrotemp = np.abs(SE_ACROPHASE[j]/(2*np.pi)) * per
		acrotemp[acrotemp>per] -= per
		ACROPHASE_SE_24[j] = acrotemp

	a = np.squeeze(ACROPHASE_24)
	a_se = np.squeeze(ACROPHASE_SE_24)
	if len(period) > 1:
		color_arr = ['r', 'g', 'b', 'y', 'c', 'k']
		legend_patch = []
		for i, a_ in enumerate(a):
			legend_patch.append(mpatches.Patch(color=color_arr[i], hatch = '|', label='Period [%1.1f]' % period[i]))
			plt.axvline(x=a_.squeeze(), color=color_arr[i], alpha = 0.2)
			plt.axvline(x=(a_ - a_se[i]), color=color_arr[i], ls=':', alpha = 0.2)
			plt.axvline(x=(a_ + a_se[i]), color=color_arr[i], ls=':', alpha = 0.2)
		plt.legend(handles=legend_patch)
	else:
		plt.axvline(x=a.squeeze(), color='k', alpha = 0.2)
		plt.axvline(x=(a - a_se), color='k', ls=':', alpha = 0.2)
		plt.axvline(x=(a + a_se), color='k', ls=':', alpha = 0.2)
	plt.xticks(list(range(25)))

	plt.subplot(2, 1, 2)
	plt.title("Histogram of F(model) values from %d permutations" % (n_perm))
	n_, bins_, patches_ =  plt.hist(Fperm, bins=50)
	txt = r"$y(t) = %1.2f $" % (MESOR)

	# F distribution null pdf line
	x = np.linspace(f.ppf(0.001, DF_Between, DF_Within),f.ppf(0.999, DF_Between, DF_Within), 1000)
	plt.plot(x, f.pdf(x, DF_Between, DF_Within) * sum(n_ * np.diff(bins_)), ls = ':', c = 'k', alpha = 0.5)

	for i, per in enumerate(period):
		txt += r"$+ %1.3f\mathrm{cos} (2 \pi (t)/%d %1.3f)$" % (AMPLITUDE[i], per, ACROPHASE[i])

	if np.squeeze(Fmodel) > Fperm.max():
		pp_text = r'$\mathrm{p(permuted)} < 0.0001$'
	else:
		p_array=np.zeros((n_perm))
		for j in range(n_perm):
			p_array[j] = np.true_divide(j,n_perm)
		stat_loc = np.searchsorted(np.sort(Fperm.squeeze()), Fmodel, side="right")
		pp = 1 - p_array[stat_loc]
		pp_text = r'$\mathrm{p(permuted)} = %1.3e$' % pp

	critF = np.sort(Fperm.squeeze())[::-1][int(0.05*n_perm)]
	textstr = '\n'.join((
		txt,
		r'R^2 = %1.2f' % R2,
		r'F(%d,%d) = %1.2f' % (DF_Between, DF_Within, Fmodel),
		r'F(alpha=0.05) = %1.2f' % (critF),
		r'$\mathrm{p(parametric)}=%1.3e$' % (f.sf(Fmodel, DF_Between, DF_Within)),
		pp_text))

	left, width = .25, .5
	bottom, height = .25, .5
	right = left + width
	top = bottom + height
	plt.text(0.6 - ((len(period)-1)*0.12), 0.6, textstr,
					transform=plt.gca().transAxes,
					bbox=dict(facecolor='b', alpha=0.1))
	plt.axvline(x=critF, color='k', alpha = 0.2)
	if Fmodel > critF:
		plt.axvline(x=Fmodel, color='g', alpha = .8, ls = '--')
	else:
		plt.axvline(x=Fmodel, color='r', alpha = .8, ls = '--')
	plt.savefig(outname, transparent=False, bbox_inches='tight')
	plt.close()

def lm_residuals(endog, exog):
	"""
	"""
	if exog.ndim == 1:
		exog = stack_ones(exog)
	if np.mean(exog[:,0]) != 1:
		exog = stack_ones(exog)
	a = cy_lin_lstsqr_mat(exog,endog)
	endog = endog - np.dot(exog,a)
	return endog


def project_cosionor_model(MESOR, AMPLITUDE, ACROPHASE, TIME_VAR, PERIOD = [24.0]):
	TIME_VAR = np.array(TIME_VAR)
	n = len(TIME_VAR)
	try:
		r = len(MESOR)
	except:
		r = 1
	proj = MESOR
	for j, per in enumerate(PERIOD):
		proj = proj + AMPLITUDE[j,:]*np.cos((np.divide(2*np.pi*np.tile(TIME_VAR,r).reshape(r,n).T, per) + ACROPHASE[j,:]))
	return proj


def residual_cosinor(endog, time_var, period = [24.0]):
	n = endog.shape[0]
	num_period = len(period)
	exog_vars = np.ones((n))
	for i in range(num_period):
		exog_vars = np.column_stack((exog_vars,np.cos(np.divide(2.0*np.pi*time_var, period[i]))))
		exog_vars = np.column_stack((exog_vars,np.sin(np.divide(2.0*np.pi*time_var, period[i]))))
	return np.array(lm_residuals(endog, exog_vars))


def periodogram(endog, time_variable, periodrange = [3, 24], step = 1.0, save_plot = False, outname = 'periodogram_plot.png'):
	# Check that endog has two dimensions
	if endog.ndim == 1:
		endog = endog.reshape(len(endog),1)

	periods =  np.arange(periodrange[0],(periodrange[1]+step),step)
	coeff = []
	for period in periods:
		period = [period]
		R2 = glm_cosinor(endog = endog, time_var = time_variable, period = period, calc_MESOR = True, output_fit_only = False)[0]
		if R2 < 0:
			R2 = 0
		coeff.append(R2)
	if save_plot:
		plt.plot(periods, coeff)
		plt.ylabel("R-squared of cosinor model")
		plt.xlabel("Period")
		plt.xticks(np.arange(0, (periodrange[1]+step), step))
		plt.grid(True)
		plt.title("Periodogram")
		plt.savefig(outname, transparent=False, bbox_inches='tight')
		plt.close()


def sliding_window_cosinor(endog, time_variable, subset_size = 24, period = [24.0], save_plot = False, outname = 'sliding_window_plot.png'):
	if endog.ndim == 1:
		endog = endog.reshape(len(endog),1)

	n_steps = (len(time_variable) - subset_size)
	step_R2 = []
	step_mesor = []
	step_mesor_SE = []
	step_ampl = []
	step_ampl_SE = []
	step_acro24 = []
	step_neglogp = []
	steps = []

	for i in range(n_steps):
		temp_time = time_variable[i:int(i+subset_size)]
		temp_endog = endog[i:int(i+subset_size),0]

		n = len(temp_endog)
		k = len(period)*2 + 1
		DF_Between = k - 1 # aka df model
		DF_Within = n - k # aka df residuals

		R2, MESOR, SE_MESOR, AMPLITUDE, SE_AMPLITUDE, ACROPHASE, SE_ACROPHASE, Fmodel = glm_cosinor(endog = temp_endog, 
									time_var = temp_time,
									period = period,
									calc_MESOR = True,
									output_fit_only = False)[:8]
		ACROPHASE_24 = np.zeros_like(ACROPHASE)
		for j, per in enumerate(period):
			acrotemp = np.abs(ACROPHASE[j]/(2*np.pi)) * per
			acrotemp[acrotemp>per] -= per
			ACROPHASE_24[j] = acrotemp

		step_R2.append(np.squeeze(R2))
		step_mesor.append(np.squeeze(MESOR))
		step_mesor_SE.append(np.squeeze(SE_MESOR))
		step_ampl.append(np.squeeze(AMPLITUDE))
		step_ampl_SE.append(np.squeeze(SE_AMPLITUDE))
		step_acro24.append(np.squeeze(ACROPHASE_24))
		step_neglogp.append(-np.log10(f.sf(Fmodel, DF_Between, DF_Within)))
		steps.append(i+1)
	if save_plot:
		step_R2 = np.array(step_R2)
		step_mesor =  np.array(step_mesor)
		step_mesor_SE =  np.array(step_mesor_SE)
		step_ampl =  np.array(step_ampl)
		step_ampl_SE =  np.array(step_ampl_SE)
		step_acro24 = np.array(step_acro24)
		step_neglogp =  np.array(step_neglogp)

		plt.figure(figsize=(12,24))
		plt.subplot(5, 1, 1)
		plt.plot(steps, step_R2)
		plt.title('Sliding window plots')
		plt.ylabel('R-sqr')
		plt.gca().yaxis.set_major_formatter(StrMethodFormatter('{x:,.2f}'))
		plt.xticks(steps)
		plt.grid(True)

		plt.subplot(5, 1, 2)
		plt.plot(steps, step_mesor)
		plt.fill_between(steps, step_mesor - step_mesor_SE, step_mesor + step_mesor_SE, alpha=0.2, color='k')
		plt.ylabel('MESOR')
		plt.gca().yaxis.set_major_formatter(StrMethodFormatter('{x:,.2f}'))
		plt.xticks(steps)
		plt.grid(True)

		plt.subplot(5, 1, 3)
		plt.plot(steps, step_ampl)
		if len(period) == 1:
			plt.fill_between(steps, 
								step_ampl - step_ampl_SE,
								step_ampl + step_ampl_SE,
								alpha=0.2,
								color='k')
		plt.ylabel('Amplitude')
		plt.gca().yaxis.set_major_formatter(StrMethodFormatter('{x:,.2f}'))
		plt.xticks(steps)
		plt.grid(True)

		plt.subplot(5, 1, 4)
		plt.plot(steps, step_acro24)
		plt.ylabel('Acrophase [24h]')
		plt.gca().yaxis.set_major_formatter(StrMethodFormatter('{x:,.1f}'))
		plt.xticks(steps)
		plt.grid(True)

		plt.subplot(5, 1, 5)
		plt.plot(steps, step_neglogp)
		plt.ylabel('-logP')
		plt.axhline(y=-np.log10(0.05), color='k', linestyle=':')
		plt.gca().yaxis.set_major_formatter(StrMethodFormatter('{x:,.2f}'))
		plt.xticks(steps)
		plt.xlabel("Step (size = %d)" % subset_size)
		plt.grid(True)
		plt.savefig(outname, transparent=False, bbox_inches='tight')
		plt.close()

def plot_cosinor_simulations(endog, time_variable, period = [24.0], n_simulations = 200, randomise_time = False, resample_eveningly = False, n_sampling = None, range_sampling = None, outbasename = 'cosinor_simulation_plot'):
	n = len(endog)

	arr_xtick = np.arange(0, 25, 1)

	resids = residual_cosinor(endog = endog, time_var = time_variable, period = period)
	plt.scatter(time_variable, resids, marker = '.', color='k')
	plt.axhline(y=0, color='k')
	plt.axhline(y=resids.std(), color='k', ls = ":")
	plt.axhline(y=-resids.std(), color='k', ls = ":")
	plt.xticks(arr_xtick)
	plt.title('Residuals of Cosinor Model')

	max_r = resids.max()
	min_r = resids.min()
	plt.ylim(min_r*1.2, max_r*1.2)

	plt.savefig("%s_residuals.png" % outbasename, transparent=False, bbox_inches='tight')
	plt.close()

	R2, MESOR, SE_MESOR, AMPLITUDE, SE_AMPLITUDE, ACROPHASE, SE_ACROPHASE, Fmodel = glm_cosinor(endog = endog, 
								time_var = time_variable,
								period = period,
								calc_MESOR = True,
								output_fit_only = False)[:8]

	model_line, times = create_cosinor_fit(period, 
														np.squeeze(MESOR),
														AMPLITUDE,
														ACROPHASE,
														time_space = np.linspace(0,24,200))
	plt.figure(figsize=(12,8))
	plt.plot(times, model_line, c='k')
	plt.scatter(time_variable, endog, marker = '.')

	if randomise_time:
		if n_sampling is None:
			n_sampling = n
		if range_sampling is None:
			range_sampling = [0,23.99]
		if resample_eveningly:
			sim_time = np.linspace(range_sampling[0],range_sampling[1],n_sampling)
		else:
			sim_time = np.sort(np.random.uniform(low=range_sampling[0], high=range_sampling[1], size=(n_sampling,)))
	else:
		n_sampling = n
		sim_time = time_variable

	# the mean and std of for the noise is calculated from the residuals
	noise_mean = resids.mean()
	noise_std = resids.std()
	noise_npts = n_sampling

	for i in range(n_simulations):
		noise = np.random.normal(noise_mean, noise_std, noise_npts).reshape(noise_npts,1)
		# calculate the predicted cosinor curve
		predicted = project_cosionor_model(MESOR, AMPLITUDE, ACROPHASE, TIME_VAR = sim_time, PERIOD = period)
		sim_endog = noise + predicted
		sMESOR, sAMPLITUDE, sACROPHASE = glm_cosinor(endog = sim_endog, 
																time_var = sim_time,
																period = period,
																calc_MESOR = True,
																output_fit_only = True)


		pred_time = np.linspace(0,25, 200)
		predicted = project_cosionor_model(sMESOR, sAMPLITUDE, sACROPHASE, TIME_VAR = pred_time, PERIOD = period)
		plt.plot(pred_time, predicted, alpha = 0.2, linestyle = ':', c='k')
	plt.xticks(arr_xtick)
	plt.title('Cosinor Model + Simulated Curves')
	plt.xlabel('Time (hour)')
	plt.savefig("%s.png" % outbasename, transparent=False, bbox_inches='tight')
	plt.close()


def create_cosinor_fit(period, MESOR, AMPLITUDE, ACROPHASE, time_space = np.linspace(0,24,200)):
	if ACROPHASE.shape[1] == 1:
		model_line = MESOR
		for j, per in enumerate(period):
			model_line += float(AMPLITUDE[j]) * np.cos(np.divide((2*np.pi*time_space),per) + float(ACROPHASE[j]))
	return(model_line, time_space)


def check_columns(pdData):
	for counter, roi in enumerate(pdData.columns):
		if counter == 0:
			num_subjects = len(pdData[roi])
		a = np.unique(pdData[roi])
		num_missing = np.sum(pdData[roi].isnull()*1)
		if len(a) > 10:
			astr = '[n>10]'
		else:
			astr = ','.join(a.astype(np.str))
			astr = '['+astr+']'
		if num_missing == 0:
			print("[%d] : %s\t%s" % (counter, roi, astr))
		else:
			print("[%d] : %s\t%s\t\tCONTAINS %d MISSING VARIABLES!" % (counter, roi, astr, num_missing))


def load_vars(pdCSV, variables, exog = [], names = [], demean_flag = True):
	if len(variables) % 2 == 1:
		print("Error: each input must be followed by data type. e.g., -ic day d age c (d = discrete, c = continous)")
	num_exog = int(len(variables) / 2)
	for i in range(num_exog):
		j = i * 2 
		k = j + 1
		if variables[k] == 'c':
			print("Coding %s as continous variable" % variables[j])
			temp = dummy_code(np.array(pdCSV[variables[j]]), iscontinous = True, demean = demean_flag)
			temp = temp[:,np.newaxis]
			exog.append(temp)
		elif variables[k] == 'd':
			print("Coding %s as discrete variable" % variables[j])
			temp = dummy_code(np.array(pdCSV[variables[j]]), iscontinous = False, demean = demean_flag)
			if temp.ndim == 1:
				temp = temp[:,np.newaxis]
			exog.append(temp)
		else:
			print("Error: variable type is not understood")
		names.append(variables[j])
	return (exog, names)


def dummy_code(variable, iscontinous = False, demean = True):
	"""
	Dummy codes a variable
	
	Parameters
	----------
	variable : array
		1D array variable of any type 

	Returns
	---------
	dummy_vars : array
		dummy coded array of shape [(# subjects), (unique variables - 1)]
	
	"""
	if iscontinous:
		if demean:
			dummy_vars = variable - np.mean(variable,0)
		else:
			dummy_vars = variable
	else:
		unique_vars = np.unique(variable)
		dummy_vars = []
		for var in unique_vars:
			temp_var = np.zeros((len(variable)))
			temp_var[variable == var] = 1
			dummy_vars.append(temp_var)
		dummy_vars = np.array(dummy_vars)[1:] # remove the first column as reference variable
		dummy_vars = np.squeeze(dummy_vars).astype(np.int).T
		if demean:
			dummy_vars = dummy_vars - np.mean(dummy_vars,0)
	return dummy_vars


def stack_ones(arr):
	"""
	Add a column of ones to an array
	
	Parameters
	----------
	arr : array

	Returns
	---------
	arr : array
		array with a column of ones
	
	"""
	return np.column_stack([np.ones(len(arr)),arr])
