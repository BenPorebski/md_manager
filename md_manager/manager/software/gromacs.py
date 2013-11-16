'''
gromacs.py
Abstraction layer for setting up, checking on and performing analysis of gromacs simulations.
'''

from manager.models import ClusterJob
from datetime import datetime, timedelta
import pytz

machine_timezone = pytz.timezone("Australia/Melbourne")

def update_simulation(sim):
	print sim

	if sim.state != "Complete":
		sim.state = ""	## Reset simulation state
	sim.notes = "" ## Reset simulation notes

	## Check for a job that matches sim in ClusterJob
	for job in ClusterJob.objects.all():
		if job.job_name.find(sim.job_uuid) != -1 and job.state != "Complete":
			## If we are here - we have found a matching job.
			## Update info from job
			sim.state = job.state
			sim.last_known_jobid = job.job_id
			sim.n_cores = job.n_cores

			try:
				tmp_jobname = job.job_name.upper()
				progression = (int(tmp_jobname.split("MD")[1]) - 1) * int(sim.project.production_protocol.ns_per_block)
				sim.progression = str(progression)
			except:
				sim.progression = None

			break


	## Check for simulation completion or failure.
	if sim.state == "" or sim.simulation_rate == None:
		performance, err = sim.assigned_cluster.exec_cmd("tail %s/*.logout | grep 'Performance'" % (sim.work_dir))

		if err:
			#Error, directory doesn't exist.
			sim.notes = "Error: Cannot locate simulation working directory!"
		else:
			rate_lines = performance.split('\n')
			rate_counter = 0
			last_rate = None
			for line in rate_lines:
				if line.strip() != "":
					last_rate = line
					rate_counter += 1

			if sim.state != "Active":
				if rate_counter < sim.project.production_protocol.n_blocks:
					sim.state = "Fail"
					sim.notes = "Error: Failed at MD %d" % (rate_counter + 1)
				else:
					sim.state = "Complete"
					sim.progression = sim.project.production_protocol.total_ns

			try:
				sim.simulation_rate = round(float(last_rate.split()[3]), 3) ## ns/day
			except:
				sim.simulation_rate = None


	## Update sestimated completion date
	if sim.progression != None and sim.simulation_rate != 0 and sim.simulation_rate != None:
		estimated_completion = float(sim.project.production_protocol.total_ns - float(sim.progression))/float(sim.simulation_rate)
		sim.estimated_completion = datetime.now() + timedelta(days=estimated_completion)

		## fix timezone issue
		sim.estimated_completion = sim.estimated_completion.replace(tzinfo=machine_timezone)


	sim.save()



def request_trajectory(sim):
	print "Requesting gromacs trajectory."

	sim_name = "%s_%s" % (sim.project.name, sim.name)

	concat_file = "%s_cat.xtc" % sim_name
	concat_noh_file = "%s_cat_noh.xtc" % sim_name
	rmsd_file = "%s_rmsd.xvg" % sim_name
	config = sim.project.simulation_package

	ls_cmd = "ls -1 %s/*MD*.xtc" % sim.work_dir
	n_xtc, err = sim.assigned_cluster.exec_cmd(ls_cmd)

	n_cont = len(n_xtc.split('\n'))

	cont = ''
	for i in range(int(n_cont)):
		cont += 'c\n'
	cont += 'c'

## Concatenate trajectory
## Convert trajectory to only include protein -- Will need to change this to exclude only water...
## Create start.gro
## Generate RMSD
## Generate RMSF - To implement.
	request_cmd = """
%s -f *MD*.xtc -o %s -dt 10 -settime << EOF
%s
EOF
echo 1 1|%s -f %s -o %s -s *for_MD001.tpr -pbc nojump -center
echo 1 1|%s -f %s/EQ/*10.gro -o %s_start.gro -s %s/EQ/*10.tpr -pbc nojump -center
echo 1 3|%s -s *for_MD001.tpr -f %s -o %s
rm %s
""" % (config.gromacs_trjcat_path, concat_file,
	cont,
	config.gromacs_trjconv_path, concat_file, concat_noh_file,
	config.gromacs_trjconv_path, sim.work_dir, sim_name, sim.work_dir,
	config.gromacs_g_rms_path, concat_noh_file, rmsd_file,
	concat_file)
	
	## Write the job submission script
	jobname = sim_name + "_traj_analysis"
	script = sim.assigned_cluster.write_script(1, 4, "10:0:0", jobname, request_cmd, config.module)

	submission = sim.assigned_cluster.submit_job(script, sim.work_dir)

	sim.trajectory_state = "Requested"
	sim.trajectory_path = sim.work_dir + "/" + concat_noh_file
	sim.trajectory_job_id = submission.split(".")[0]
	sim.rmsd_path = sim.work_dir + "/" + rmsd_file

	sim.save()


def delete_trajectory(sim):
	print "Deleting gromacs trajectory"

	sim_name = "%s_%s" % (sim.project.name, sim.name)

	concat_file = "%s/%s_cat.xtc" % (sim.work_dir, sim_name)
	concat_noh_file = "%s/%s_cat_noh.xtc" % (sim.work_dir, sim_name)
	rmsd_file = "%s/%s_rmsd.xvg" % (sim.work_dir, sim_name)

	## Delete files
	rm_cmd = "rm  %s %s %s" % (concat_file, concat_noh_file, rmsd_file)
	rm, err = sim.assigned_cluster.exec_cmd(rm_cmd)

	## Update db
	sim.trajectory_state = ""
	sim.trajectory_path = ""
	sim.trajectory_job_id = ""
	sim.rmsd_path = ""
	sim.rmsd_data = ""

	sim.save()







