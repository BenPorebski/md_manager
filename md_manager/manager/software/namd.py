'''
namd.py
Abstraction layer for setting up, checking on and performing analysis of NAMD simulations.
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
				progression = (int(job.job_name.split("MD")[1]) - 1) * int(sim.project.production_protocol.ns_per_block)
				sim.progression = str(progression)
			except:
				sim.progression = None

			break

######## NAMD specific code ##########
	if sim.state == "" or sim.simulation_rate == None:
		## Check for simulation completion or failure.
		performance, err = sim.assigned_cluster.exec_cmd("tail %s/*.log | grep 'WallClock'" % (sim.work_dir))

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
				if len(rate_lines) < sim.project.production_protocol.n_blocks:
					sim.state = "Fail"
					sim.notes = "Error: Failed at %d" % (rate_counter)
				else:
					sim.state = "Complete"

			try:
				rate_ns_day = round(1/(float(last_rate.split()[1])/sim.project.production_protocol.ns_per_block/60/60/24), 3)
			except:
				rate_ns_day = None


			sim.simulation_rate = rate_ns_day ## ns/day


########## End NAMD specific code ##########

	## Update sestimated completion date
	if sim.progression != None and sim.simulation_rate != 0 and sim.simulation_rate != None:
		estimated_completion = float(sim.project.production_protocol.total_ns - float(sim.progression))/float(sim.simulation_rate)
		sim.estimated_completion = datetime.now() + timedelta(days=estimated_completion)

		## fix timezone issue
		sim.estimated_completion = sim.estimated_completion.replace(tzinfo=machine_timezone)


	sim.save()





def request_trajectory(sim):
	print "Requesting namd trajectory."

	sim_name = "%s_%s" % (sim.project.name, sim.name)

	concat_stripped_file = "%s_cat_stripped.dcd" % sim_name
	rmsd_file = "%s_rmsd.dat" % sim_name
	config = sim.project.simulation_package

	start_psf = "EQ/ionized.psf"
	start_pdb = "EQ/ionized.pdb"


	strip_waters_tcl_template = '''
set sel [atomselect top "all not water and not hydrogen"]
set outfile [open %s_stripped.ind w]
puts $outfile [$sel get index]
$sel writepdb %s_stripped.pdb
$sel writepsf %s_stripped.psf
close $outfile
''' % (sim_name, sim_name, sim_name)

	create_rmsd_tcl_template = '''
set outfile [open %s w]
set nf [molinfo top get numframes]
set frame0 [atomselect top "protein and backbone and noh" frame 0]
set sel [atomselect top "protein and backbone and noh"]
set all [atomselect top all]
# rmsd calculation loop
for { set i 1 } { $i <= $nf } { incr i } {
$sel frame $i
$all frame $i
$all move [measure fit $sel $frame0]
puts $outfile "[expr $i *250 * 2] [expr [measure rmsd $sel $frame0] / 10]"
}
close $outfile
''' % rmsd_file

	## Create the tcl scripts	
	create_tcl_scripts_cmd = "cd %s; echo -e '%s' > strip_waters.tcl; echo -e '%s' > create_rmsd.tcl" % (sim.work_dir, strip_waters_tcl_template, create_rmsd_tcl_template)
	create_scripts, err = sim.assigned_cluster.exec_cmd(create_tcl_scripts_cmd)

	## Job submission command
	vmd_concatenate_rmsd_cmd = '''
cd %s
vmd -dispdev none EQ/ionized.psf EQ/ionized.pdb < %s
%s -stride 10 -o %s -i %s_stripped.ind *prod*.dcd
vmd -dispdev none %s_stripped.psf %s < %s
''' % ( sim.work_dir,
	"strip_waters.tcl",
	config.namd_catdcd_path, concat_stripped_file, sim_name,
	sim_name, concat_stripped_file, "create_rmsd.tcl")

	## Write the job submission script
	jobname = sim_name + "_traj_analysis"
	script = sim.assigned_cluster.write_script(1, 1, "10:0:0", jobname, vmd_concatenate_rmsd_cmd, config.module)

	# print script

	submission = sim.assigned_cluster.submit_job(script, sim.work_dir)

	print submission

	sim.trajectory_state = "Requested"
	sim.trajectory_path = sim.work_dir + "/" + concat_stripped_file
	sim.trajectory_job_id = submission.split(".")[0]
	sim.rmsd_path = sim.work_dir + "/" + rmsd_file

	sim.save()




def delete_trajectory(sim):
	print "Deleting namd trajectory"

	sim_name = "%s_%s" % (sim.project.name, sim.name)

	concat_file = "%s/%s_cat_stripped.dcd" % (sim.work_dir, sim_name)
	rmsd_file = "%s/%s_rmsd.dat" % (sim.work_dir, sim_name)

	## Delete files
	rm_cmd = "rm  %s %s" % (concat_file, rmsd_file)
	rm, err = sim.assigned_cluster.exec_cmd(rm_cmd)

	## Update db
	sim.trajectory_state = ""
	sim.trajectory_path = ""
	sim.trajectory_job_id = ""
	sim.rmsd_path = ""
	sim.rmsd_data = ""

	sim.save()

