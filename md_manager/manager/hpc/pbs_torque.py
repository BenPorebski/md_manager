'''
pbs_torque.py
Abstraction layer for parsing pbs torque status information.
Status is parsed and updated here.
'''

import sys
import xml.etree.ElementTree as ET
from manager.models import ClusterJob

def update_jobs(host):
	'''
	Run qstat -x, parse the xml output and update the ClusterJobs table.
	'''

	print "Parsing qstat..."
	qstat_xml, err = host.exec_cmd("qstat -x")

	if err:
		return

	## Clear ClusterJobs that are linked to host
	ClusterJob.objects.filter(job_host=host).delete()

	## Parse qstat xml output
	root = ET.fromstring(qstat_xml)
	for child in root:
		job_id = child.find("Job_Id").text.split(".")[0]
		job_name = child.find("Job_Name").text
		job_owner = child.find("Job_Owner").text.split("@")[0]

		try:
			nodes = child.find("Resource_List").find("nodes").text
			n_nodes = int(nodes.split(':')[0])
		except:
			n_nodes = 1

		try:
			ppn = int(nodes.split(':')[1].split('=')[1])
			cores = n_nodes*ppn
		except:
			cores = n_nodes
			ppn = 1

		try:
			work_dir = child.find("init_work_dir").text
		except:
			work_dir = ""

		try:
			state_tmp = child.find("job_state").text
			state = "Unknown"
			if state_tmp == "R":
				state = "Active"
			elif state_tmp == "C":
				state = "Complete"
			elif state_tmp == "Q":
				state = "Idle"
			elif state_tmp == "H":
				state = "Hold"
			elif state_tmp == "E":
				state = "Error"
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
	Run pbsnodes -x, parse xml output and update the ClusterHost
	'''

	print "Parsing pbsnodes..."
	pbsnodes_xml, err = host.exec_cmd("pbsnodes -x")

	if err:
		return

	## Find total available procs on the cluster host.
	nodes_root = ET.fromstring(pbsnodes_xml)
	total_procs = 0
	for node in nodes_root:
		np = node.find("np").text
		state = node.find("state").text
		if state != "down" and state != "offline":
			total_procs = total_procs + int(np)


	## Find the number of active jobs and procs.
	active_jobs = 0
	active_procs = 0
	for job in ClusterJob.objects.filter(job_host=host):
		if job.state == 'Active':
			active_jobs += 1
			active_procs += job.n_cores

	## Calculate the percentage of active jobs on the cluster
	percentage_active = round(float(active_procs)/float(total_procs)*100, 2)

	host.total_procs = total_procs
	host.active_procs = active_procs
	host.percentage_active = percentage_active

	host.total_jobs = len(ClusterJob.objects.filter(job_host=host))
	host.active_jobs = active_jobs

	host.save()



## All queue abstractions MUST have an update_queue function!
def update_queue(host):
	print "Retrieving PBS Torque status information from %s" % host.hostname
	update_jobs(host)
	update_host(host)




def write_script(host, nodes, ppn, walltime, job_name, cmd, modules):
	module_line = ''
	if modules != "":
		module_line = "module load %s" % modules

	template = '''
#PBS -l nodes=%s:ppn=%s
#PBS -l walltime=%s
#PBS -N %s
#PBS -S /bin/bash

%s

cd $PBS_O_WORKDIR

%s
''' % (nodes, ppn, walltime, job_name, module_line, cmd)

	return template



def submit_job(host, script, work_dir):
	print "Submitting job to %s" % (host)

	## Change directory to work_dir
	## Submit job script to queuing system.
	cmd = "cd %s; echo -e '%s' | qsub" % (work_dir, script)
	qsub, err = host.exec_cmd(cmd)

	if err:
		return err
	else:
		return qsub

## All queue abstractions MUST have a cancel_job function!
def cancel_job(host, job_id):
	print "Cancelling job %s on %s" % (job_id, host.hostname)

	cmd = "qdel %s" % job_id
	qdel, err = host.exec_cmd(cmd)

	if err:
		return err
	else:
		return qdel




