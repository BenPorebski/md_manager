from django.db import models
from django.contrib.auth.models import User
import paramiko
import sys

class ClusterHost(models.Model):
	name = models.TextField()
	username = models.TextField()
	hostname = models.TextField()
	qstat_cmd = models.TextField()
	queue_system = models.TextField()

	total_procs = models.IntegerField(blank=True, null=True)
	active_procs = models.IntegerField(blank=True, null=True)
	percentage_active = models.FloatField(blank=True, null=True)

	total_jobs = models.IntegerField(blank=True, null=True)
	active_jobs = models.IntegerField(blank=True, null=True)


	def __unicode__(self):
		return "{0}@{1}".format(self.username, self.hostname)


	def exec_cmd(self, command):
		client = paramiko.SSHClient()
		client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
		client.connect(hostname=self.hostname, username=self.username, allow_agent=True)
		stdin, stdout, stderr = client.exec_command(command)
		retout = stdout.read()
		reterr = stderr.read()
		return (retout, reterr)

	def update_queue(self):
		sys.path.append("manager/hpc/")
		module = __import__(self.queue_system)
		return module.update_queue(self)

	def write_script(self, nodes, ppn, walltime, job_name, cmd, modules):
		sys.path.append("manager/hpc/")
		module = __import__(self.queue_system)
		return module.write_script(self, nodes, ppn, walltime, job_name, cmd, modules)

	def submit_job(self, script, work_dir):
		sys.path.append("manager/hpc/")
		module = __import__(self.queue_system)
		return module.submit_job(self, script, work_dir)

	def cancel_job(self, job_id):
		sys.path.append("manager/hpc/")
		module = __import__(self.queue_system)
		return module.cancel_job(self, job_id)


class ClusterJob(models.Model):
	job_id = models.IntegerField(blank=True, null=True)
	job_name = models.TextField()
	job_owner = models.TextField()
	job_host = models.ForeignKey(ClusterHost)
	n_cores = models.IntegerField()
	state = models.TextField()
	work_dir = models.TextField()

	def __unicode__(self):
		return "{0}@{1}".format(self.job_id, self.job_host.hostname)



class SoftwareConfig(models.Model):
	name = models.TextField()
	package = models.TextField()
	cluster = models.ForeignKey(ClusterHost)

	module = models.TextField(blank=True)

	## Gromacs config params
	gromacs_trjconv_path = models.TextField(blank=True)
	gromacs_trjcat_path = models.TextField(blank=True)
	gromacs_g_rms_path = models.TextField(blank=True)

	## NAMD config params
	namd2_path = models.TextField(blank=True)
	namd_catdcd_path = models.TextField(blank=True)

	def __unicode__(self):
		return "{0}@{1}".format(self.name, self.cluster)



class EquilibrationProtocol(models.Model):
	name = models.TextField()
	description = models.TextField(blank=True)


	def __unicode__(self):
		return "{0} :: {1}".format(self.id, self.name)


class ProductionProtocol(models.Model):
	name = models.TextField()
	description = models.TextField(blank=True)

	n_blocks = models.IntegerField(blank=True, null=True)
	steps_per_block = models.IntegerField(blank=True, null=True)

	timestep = models.FloatField(blank=True, null=True) # fs

	ns_per_block = models.FloatField(blank=True, null=True)	## steps_per_block * timestep :: Units of ns
	total_ns = models.FloatField(blank=True, null=True)	## ns_per_block * n_blocks  :: Units of ns

	def __unicode__(self):
		return "{0} :: {1}".format(self.id, self.name)


class Project(models.Model):
	name = models.TextField()
	notes = models.TextField(blank=True)
	## All simulaiton parameters should be stored here.
	simulation_package = models.ForeignKey(SoftwareConfig, blank=True, null=True)

	equilibration_protocol = models.ForeignKey(EquilibrationProtocol, blank=True, null=True)
	production_protocol = models.ForeignKey(ProductionProtocol, blank=True, null=True)

	def __unicode__(self):
		return "{0} :: {1}".format(self.id, self.name)


class Simulation(models.Model):
	name = models.TextField()
	job_uuid = models.TextField()
	last_known_jobid = models.TextField(blank=True)
	project = models.ForeignKey(Project)
	assigned_cluster = models.ForeignKey(ClusterHost)
	work_dir = models.TextField() ## Absolute location
	state = models.TextField(blank=True) ## Active, Idle, Failed, Completed
	notes = models.TextField(blank=True)

	start_time = models.DateTimeField(auto_now_add=True)
	estimated_completion = models.DateTimeField(blank=True, null=True)
	progression = models.IntegerField(blank=True, null=True)	## ns (completed_blocks * project.production_protocol.ns_per_block)
	simulation_rate = models.FloatField(blank=True, null=True) ## ns/day
	n_cores = models.IntegerField(blank=True, null=True)
	last_status_update = models.DateTimeField(auto_now=True)

	## Analysis information ##

	## Trajectories will need to be downloaded to md_manager or proxied...
	trajectory_state = models.TextField(blank=True)
	trajectory_path = models.TextField(blank=True)
	trajectory_job_id = models.TextField(blank=True)

	rmsd_state = models.TextField(blank=True)
	rmsd_path = models.TextField(blank=True)
	rmsd_job_id = models.TextField(blank=True)
	rmsd_data = models.TextField(blank=True)

	def __unicode__(self):
		return "{0} :: {1}-{2}".format(self.id, self.project.name, self.name)

	def update_simulation(self):
		sys.path.append("manager/software/")
		module = __import__(self.project.simulation_package.package)
		return module.update_simulation(self)

	def request_trajectory(self):
		sys.path.append("manager/software/")
		module = __import__(self.project.simulation_package.package)
		return module.request_trajectory(self)

	def delete_trajectory(self):
		sys.path.append("manager/software/")
		module = __import__(self.project.simulation_package.package)
		return module.delete_trajectory(self)






class UserProfile(models.Model):
	user = models.OneToOneField(User)

	def __unicode__(self):
		return self.user.username

