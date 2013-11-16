# URL mappings for MD manager main app
from django.conf.urls import patterns, include, url
from manager import views

urlpatterns = patterns('',
   	url(r'^$', views.IndexView.as_view(), name='index'),
   	url(r'^cluster_status$', views.cluster_status, name='cluster_status'),

   	url(r'^view_simulations$', views.view_simulations, name='view_simulations'),
   	url(r'^update_simulations$', views.update_simulations, name='update_simulations'),
   	url(r'^update_simulations/(?P<project_id>\d+)$', views.update_simulations, name='update_simulations'),

   	url(r'^view_analysis/(?P<project_id>\d+)$', views.view_analysis, name='view_analysis'),
   	url(r'^request_trajectory/(?P<project_id>\d+)$', views.request_trajectory, name='request_trajectory'),
   	url(r'^request_trajectory/(?P<project_id>\d+)/(?P<sim_id>\d+)$', views.request_trajectory, name='request_trajectory'),
   	url(r'^delete_trajectory/(?P<sim_id>\d+)$', views.delete_trajectory, name='delete_trajectory'),
   	url(r'^request_rmsd/(?P<project_id>\d+)$', views.request_rmsd, name='request_rmsd'),
   	url(r'^request_rmsd/(?P<project_id>\d+)/(?P<sim_id>\d+)$', views.request_rmsd, name='request_rmsd'),
   	url(r'^render_rmsd/(?P<project_id>\d+).png$', views.render_rmsd, name='render_rmsd'),

   	url(r'^update_analysis/(?P<project_id>\d+)$', views.update_analysis, name='update_analysis'),
   	url(r'^update_analysis/(?P<project_id>\d+)/(?P<sim_id>\d+)$', views.update_analysis, name='update_analysis'),

   	url(r'^create_simulation$', views.create_simulation, name='create_simulation'),
)