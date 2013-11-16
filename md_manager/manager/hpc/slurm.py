'''
slurm.py
Abstraction layer for parsing SLURM status information.
Status is parsed and updated here.
'''

import sys
from manager.models import ClusterJob

def update_jobs(host):
	'''
	Run scontrol, parse the output and update the ClusterJobs table.
	'''

	print "Parsing scontrol..."
	scontrol_data, err = host.exec_cmd("scontrol -d -o show job")

	if err:
		return

	## Clear ClusterJobs that are linked to host
	ClusterJob.objects.filter(job_host=host).delete()


	scontrol_split = scontrol_data.split('\n')


	for job_string in scontrol_split:

		parsed_job = {}

		for item in job_string.split():
			# print item.lower()
			partition = item.lower().partition('=')
			parsed_job[partition[0]] = partition[2]

		if 'jobid' in parsed_job:
			job_id = parsed_job['jobid']
			job_name = parsed_job['name']
			job_owner = parsed_job['userid'].split("(")[0]
			cores = parse_sinfo_number(parsed_job['numcpus'].split('-')[0])
			work_dir = parsed_job['workdir']

			try:
				state = parsed_job['jobstate'].capitalize()
				if state == "Running":
					state = "Active"
				if state == "Pending":
					state = "Idle"
			except:
				state = "Unknown"

			## Insert job into ClusterJob table.
			job = ClusterJob(
				job_id = job_id,
				job_name = job_name,
				job_owner = job_owner,
				job_host = host,
				n_cores = cores,
				work_dir = work_dir,
				state = state)

			job.save()







def update_host(host):
	'''
	Run sinfo, parse output and update the ClusterHost
	'''

	print "Parsing sinfo..."
	sinfo_string, err = host.exec_cmd('sinfo -o \'%C\' -h')

	if err:
		return

	## Parse the first line only.
	sinfo_proc_list = sinfo_string.split('\n')[0]
	proc_info = parse_sinfo(sinfo_proc_list)

	## Find total available procs on the cluster host.
	##   (not down, or offline)
	total_procs = 0
	total_procs = proc_info['total'] - proc_info['other']

	## Find the number of active jobs and procs.
	active_jobs = 0
	active_procs = 0
	for job in ClusterJob.objects.filter(job_host=host):
		if job.state == 'Active':
			active_jobs += 1
			active_procs += job.n_cores

	## Calculate the percentage of active jobs on the cluster
	percentage_active = round(100*float(active_procs)/float(total_procs), 2)

	host.total_procs = total_procs
	host.active_procs = active_procs
	host.percentage_active = percentage_active

	host.total_jobs = len(ClusterJob.objects.filter(job_host=host))
	host.active_jobs = active_jobs

	host.save()


def parse_sinfo(sinfo):
	entry = sinfo.split('/')

	statusdict = dict(
		alloc = parse_sinfo_number(entry[0]),
		idle = parse_sinfo_number(entry[1]),
		other = parse_sinfo_number(entry[2]),
		total = parse_sinfo_number(entry[3])
		)

	return statusdict

def parse_sinfo_number(nstr):
	if not nstr.isdigit():
		nstr_l = int(nstr[:-1])
		nstr_r = nstr[-1:]
		if nstr_r == 'K' or 'k':
			nstr_r = 2 ** 10
		elif nstr_r == 'M' or 'm':
			nstr_r = 2 ** 20
		elif nstr_r == 'G':
			nstr_r = 2 ** 30
		else:
			print nstr
			#raise Exception
		nstr = nstr_l * nstr_r

	return int(nstr)




## All queue abstractions MUST have an update_queue function!
def update_queue(host):
	print "Retrieving SLURM status information from %s" % host.hostname
	update_jobs(host)
	update_host(host)


## All queue abstractions MUST have an write_script function!
def write_script(host, nodes, ppn, walltime, job_name, cmd, modules):
	module_line = ''
	if modules != "":
		module_line = "module load %s" % modules

	template = '''#!/bin/bash
#SBATCH --job-name=%s
#SBATCH --nodes=%s
#SBATCH --time=%s
#SBATCH --output="%s.log"
#SBATCH --error="%s.err"

%s

%s
''' % (job_name, nodes, walltime, job_name, job_name, module_line, cmd)

	return template


## All queue abstractions MUST have a submit_job function!
def submit_job(host, script, work_dir):
	print "Submitting job to %s" % (host)

	## Change directory to work_dir
	## Submit job script to queuing system.
	cmd = "cd %s; echo -e '%s' | sbatch" % (work_dir, script)
	sbatch, err = host.exec_cmd(cmd)

	if err:
		return err
	else:
		return sbatch

## All queue abstractions MUST have a cancel_job function!
def cancel_job(host, job_id):
	print "Cancelling job %s on %s" % (job_id, host.hostname)

	cmd = "scancel %s" % job_id
	scancel, err = host.exec_cmd(cmd)

	if err:
		return err
	else:
		return scancel



