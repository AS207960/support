from django.urls import path
from . import views

urlpatterns = [
    path('', views.views.index, name='index'),
    path('new/', views.views.new_ticket, name='new_ticket'),
    path('tickets/', views.views.tickets, name='tickets'),
    path('tickets/<str:ticket_id>/', views.views.ticket, name='view-ticket'),
    path('tickets/<str:ticket_id>/verify/', views.views.verify_ticket_alt, name='verify-ticket-alt'),
    path('verify_ticket/<str:verification_token>/', views.views.verify_ticket, name='verify_ticket'),
    path('kyc/<str:session_id>/', views.views.do_kyc, name='do-kyc'),

    path('agent/tickets/', views.admin.open_tickets, name='agent-open-tickets'),
    path('agent/tickets/closed/', views.admin.closed_tickets, name='agent-closed-tickets'),
    path('agent/tickets/answered/', views.admin.answered_tickets, name='agent-answered-tickets'),
    path('agent/tickets/own/', views.admin.own_tickets, name='agent-own-tickets'),

    path('agent/tickets/new/', views.admin.create_ticket, name='agent-create-ticket'),

    path('agent/tickets/<str:ticket_id>/', views.admin.view_ticket, name='agent-view-ticket'),
    path('agent/tickets/<str:ticket_id>/edit/', views.admin.edit_ticket, name='agent-edit-ticket'),
    path('agent/tickets/<str:ticket_id>/claim/', views.admin.claim_ticket, name='agent-claim-ticket'),
    path('agent/tickets/<str:ticket_id>/close/', views.admin.close_ticket, name='agent-close-ticket'),
    path('agent/tickets/<str:ticket_id>/reopen/', views.admin.reopen_ticket, name='agent-reopen-ticket'),
    path('agent/tickets/<str:ticket_id>/delete/', views.admin.delete_ticket, name='agent-delete-ticket'),
    path('agent/tickets/<str:ticket_id>/assign/', views.admin.assign_ticket, name='agent-assign-ticket'),

    path('webhook/postal/', views.webhooks.postal_webhook),
    path('webhook/stripe/', views.webhooks.stripe_webhook),
]
