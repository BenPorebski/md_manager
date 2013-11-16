# manager views
from django.http import HttpResponse, HttpResponseRedirect, Http404
from django.shortcuts import render, render_to_response, get_object_or_404, redirect
from django.views import generic

class IndexView(generic.TemplateView):
	template_name = "index.html"

def cluster_status(request):
	from manager.models import ClusterHost
	from manager.models import ClusterJob

	## Update ClusterJobs for all ClusterHosts
	## Eventually move this to a button...
	for host in ClusterHost.objects.all():
		host.update_queue()

	return render_to_response("job_views/cluster_status.html", { "clusterjobs": ClusterJob.objects.all().order_by('job_owner', 'n_cores'),
																	"clusterhosts": ClusterHost.objects.all() })



def view_simulations(request):
	from manager.models import Simulation
	from manager.models import Project
	return render_to_response("job_views/view_simulations.html", { "projects": Project.objects.all(),
																	"simulations": Simulation.objects.all() })
def update_simulations(request, project_id=None):
	from django.http import HttpResponseRedirect
	from manager.models import Project
	from manager.models import Simulation
	from manager.models import ClusterHost

	## Update all clusters first
	for host in ClusterHost.objects.all():
		host.update_queue()

	## Perform the update here
	if project_id == None:
		## Update all simulations
		for project in Project.objects.all():
			for sim in project.simulation_set.all():
				sim.update_simulation()
	else:
		for sim in Project.objects.get(id=project_id).simulation_set.all():
		## Update specific project
			sim.update_simulation()

	## Redirect to view_simulations page
	return HttpResponseRedirect("/view_simulations")





def view_analysis(request, project_id):
	from manager.models import Project

	project_trajectory_state = ''
	for sim in Project.objects.get(id=project_id).simulation_set.all():
		if sim.trajectory_state == 'Ready':
			project_trajectory_state = sim.trajectory_state
			break

	for sim in Project.objects.get(id=project_id).simulation_set.all():
		if sim.trajectory_state == 'Requested':
			project_trajectory_state = sim.trajectory_state
			break

	render_rmsd = False
	for sim in Project.objects.get(id=project_id).simulation_set.all():
		if sim.rmsd_data != "":
			render_rmsd = True

	return render_to_response("analysis_views/view_analysis.html", { "project": Project.objects.get(id=project_id),
																	"project_trajectory_state": project_trajectory_state,
																	"render_rmsd": render_rmsd })






def request_trajectory(request, project_id, sim_id=None):
	from manager.models import Project
	from manager.models import Simulation

	if sim_id == None:
		## Request trajectories for all simulations in the project
		print "Requesting all trajectories!"
		for sim in Project.objects.get(id=project_id).simulation_set.all():
			sim.request_trajectory()
	else:
		## Request traj for particular simulation
		print "Requesting traj for simulation %s" % sim_id
		Simulation.objects.get(id=sim_id).request_trajectory()

	return HttpResponseRedirect(request.META.get('HTTP_REFERER'))

def delete_trajectory(request, sim_id):
	from manager.models import Simulation

	Simulation.objects.get(id=sim_id).delete_trajectory()

	return HttpResponseRedirect(request.META.get('HTTP_REFERER'))


def request_rmsd(request, project_id, sim_id=None):
	from manager.models import Project
	from manager.models import Simulation

	if sim_id == None:
		## Collect rmsd for all simulations
		print "blah"
		# for sim in Project.objects.get(id=project_id).simulation_set.all():
		# 	sim.request_trajectory()
	else:
		## Request rmsd for particular simulation
		sim = Simulation.objects.get(id=sim_id)
		cmd = "cat %s" % sim.rmsd_path
		rmsd_data, err = sim.assigned_cluster.exec_cmd(cmd)

		if not err:
			sim.rmsd_data = rmsd_data
			sim.save()

	return HttpResponseRedirect(request.META.get('HTTP_REFERER'))

def render_rmsd(request, project_id):
	from manager.models import Project
	from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
	from matplotlib.figure import Figure

	## Yay, drawing an RMSD plot!

	project = Project.objects.get(id=project_id)

	fig=Figure()
	fig.patch.set_alpha(0.0)
	ax=fig.add_subplot(111)

	x_max = 0
	for sim in project.simulation_set.all().order_by('name'):
		x=[]
		y=[]
		if sim.rmsd_data != "":
			for line in sim.rmsd_data.split('\n'):
				if len(line) > 0:
					if line[0] not in ('#', '@'):
						x_tmp = (float(line.split()[0])/1000.0)
						x.append(x_tmp)
						y.append(line.split()[1])
						if x_tmp > x_max:
							x_max = x_tmp
			ax.plot(x, y, label=sim.name)

	ax.set_xlim(0.0, x_max)
	# ax.set_ylim(0.0, 1.0)
	ax.set_ylabel('RMSD (nm)')
	ax.set_xlabel('Time (ns)')
	ax.set_title('RMSD plot\nC-alpha after lsq fit to %s' % project.name)
	ax.legend(loc='upper left', shadow=True)
	ax.grid(True)




	canvas=FigureCanvas(fig)
	response=HttpResponse(content_type='image/png')
	canvas.print_png(response)


	return response



def update_analysis(request, project_id, sim_id=None):
	from manager.models import Project
	from manager.models import Simulation
	from manager.models import ClusterJob

	project = Project.objects.get(id=project_id)

	if sim_id == None:
		## Update all simulation host queues
		host_lst = []
		for sim in project.simulation_set.all():
			host_lst.append(sim.assigned_cluster)
		uhost_lst = list(set(host_lst))
		for host in uhost_lst:
			host.update_queue()

		## Update all simulations in project
		for sim in project.simulation_set.all():
			if sim.trajectory_state == "Requested":
				tmp_state = ''
				for job in ClusterJob.objects.all():
					if sim.trajectory_job_id == str(job.job_id) and job.state == "Active" or "Idle":
						tmp_state = "Requested"
						break
					else:
						tmp_state = "Ready"

				sim.trajectory_state = tmp_state
				sim.save()

	else:
		## Update specific queue
		Simulation.objects.get(id=sim_id).assigned_cluster.update_queue()

		## Update trajectory states from the current stored clusterjobs
		sim = Simulation.objects.get(id=sim_id)
		if sim.trajectory_state == "Requested":
			tmp_state = ''
			for job in ClusterJob.objects.all():
				if sim.trajectory_job_id == str(job.job_id) and job.state == "Active":
					tmp_state = "Requested"
					break
				else:
					tmp_state = "Ready"

			sim.trajectory_state = tmp_state
			sim.save()

	return HttpResponseRedirect(request.META.get('HTTP_REFERER'))


def create_simulation(request):
	return render_to_response("simulations/create_new.html")





