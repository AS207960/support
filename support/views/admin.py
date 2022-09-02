from django.shortcuts import render, get_object_or_404, redirect
from .. import forms, models, tasks
from django.db.models import OuterRef, Subquery, Q
from django.core.paginator import Paginator
from django.contrib.auth.decorators import permission_required, login_required


@login_required
@permission_required('support.view_ticket', raise_exception=True)
def open_tickets(request):
    newest_message = models.TicketMessage.objects.filter(ticket=OuterRef('pk'))\
        .order_by('-date')
    tickets = models.Ticket.objects.annotate(newest_message_type=Subquery(newest_message.values('type')[:1]))\
        .filter(newest_message_type=models.TicketMessage.TYPE_CUSTOMER)\
        .filter(state=models.Ticket.STATE_OPEN)
    tickets = Paginator(tickets, 10)

    page_number = request.GET.get('page')
    page_obj = tickets.get_page(page_number)

    return render(request, "support/admin/tickets.html", {
        "tickets": page_obj,
        "tickets_type": "open"
    })


@login_required
@permission_required('support.view_ticket', raise_exception=True)
def answered_tickets(request):
    newest_message = models.TicketMessage.objects.filter(ticket=OuterRef('pk'))\
        .order_by('-date')
    tickets = models.Ticket.objects.annotate(newest_message_type=Subquery(newest_message.values('type')[:1]))\
        .filter(~Q(newest_message_type=models.TicketMessage.TYPE_CUSTOMER))\
        .filter(state=models.Ticket.STATE_OPEN)

    tickets = Paginator(tickets, 10)

    page_number = request.GET.get('page')
    page_obj = tickets.get_page(page_number)

    return render(request, "support/admin/tickets.html", {
        "tickets": page_obj,
        "tickets_type": "answered"
    })


@login_required
@permission_required('support.view_ticket', raise_exception=True)
def own_tickets(request):
    tickets = models.Ticket.objects.filter(assigned_to=request.user)

    tickets = Paginator(tickets, 10)

    page_number = request.GET.get('page')
    page_obj = tickets.get_page(page_number)

    return render(request, "support/admin/tickets.html", {
        "tickets": page_obj,
        "tickets_type": "own"
    })


@login_required
@permission_required('support.view_ticket', raise_exception=True)
def closed_tickets(request):
    tickets = models.Ticket.objects.filter(state=models.Ticket.STATE_CLOSED)

    tickets = Paginator(tickets, 10)

    page_number = request.GET.get('page')
    page_obj = tickets.get_page(page_number)

    return render(request, "support/admin/tickets.html", {
        "tickets": page_obj,
        "tickets_type": "closed"
    })


@login_required
@permission_required('support.view_ticket', raise_exception=True)
def view_ticket(request, ticket_id):
    ticket = get_object_or_404(models.Ticket, id=ticket_id)

    ticket_reply_form = forms.TicketReplyForm()
    ticket_note_form = forms.TicketNoteForm()

    if ticket.state == ticket.STATE_CLOSED:
        ticket_reply_form.fields['close'].label = "Reopen on reply"

    if request.method == "POST":
        if request.POST.get("type") == "ticket_reply":
            ticket_reply_form = forms.TicketReplyForm(request.POST)
            if ticket_reply_form.is_valid():
                tasks.post_reply(ticket, ticket_reply_form.cleaned_data['message'], request.user)
                if ticket_reply_form.cleaned_data['close']:
                    if ticket.state != ticket.STATE_CLOSED:
                        tasks.close_ticket(ticket)
                    else:
                        tasks.reopen_ticket(ticket)
                ticket_reply_form = forms.TicketReplyForm()
        elif request.POST.get("type") == "ticket_note":
            ticket_note_form = forms.TicketNoteForm(request.POST)
            if ticket_note_form.is_valid():
                tasks.post_note(ticket, ticket_note_form.cleaned_data['message'])
                ticket_note_form = forms.TicketNoteForm()

    return render(request, "support/admin/ticket.html", {
        "ticket": ticket,
        "ticket_reply_form": ticket_reply_form,
        "ticket_note_form": ticket_note_form,
    })


@login_required
@permission_required('support.change_ticket', raise_exception=True)
def edit_ticket(request, ticket_id):
    ticket = get_object_or_404(models.Ticket, id=ticket_id)

    if request.method == "POST":
        ticket_edit_form = forms.TicketEditForm(request.POST, instance=ticket)
        if ticket_edit_form.is_valid():
            ticket_edit_form.save()
            return redirect('agent-view-ticket', ticket.id)
    else:
        ticket_edit_form = forms.TicketEditForm(instance=ticket)

    return render(request, "support/admin/edit_ticket.html", {
        "ticket": ticket,
        "ticket_edit_form": ticket_edit_form
    })


@login_required
@permission_required('support.change_ticket', raise_exception=True)
def claim_ticket(request, ticket_id):
    ticket = get_object_or_404(models.Ticket, id=ticket_id)

    if request.method == "POST":
        if request.POST.get("claim") == "true":
            tasks.claim_ticket(ticket, request.user)
            return redirect('agent-view-ticket', ticket.id)

    return render(request, "support/admin/claim_ticket.html", {
        "ticket": ticket,
    })


@login_required
@permission_required('support.change_ticket', raise_exception=True)
def close_ticket(request, ticket_id):
    ticket = get_object_or_404(models.Ticket, id=ticket_id)

    if ticket.state == ticket.STATE_CLOSED:
        return redirect('agent-view-ticket', ticket.id)

    if request.method == "POST":
        ticket_close_form = forms.TicketCloseForm(request.POST)
        if ticket_close_form.is_valid():
            tasks.close_ticket(ticket, ticket_close_form.cleaned_data['message'])
            return redirect('agent-view-ticket', ticket.id)
    else:
        ticket_close_form = forms.TicketCloseForm()

    return render(request, "support/admin/close_ticket.html", {
        "ticket": ticket,
        "ticket_close_form": ticket_close_form
    })


@login_required
@permission_required('support.change_ticket', raise_exception=True)
def reopen_ticket(request, ticket_id):
    ticket = get_object_or_404(models.Ticket, id=ticket_id)

    if ticket.state == ticket.STATE_OPEN:
        return redirect('agent-view-ticket', ticket.id)

    if request.method == "POST":
        ticket_reopen_form = forms.TicketReopenForm(request.POST)
        if ticket_reopen_form.is_valid():
            tasks.reopen_ticket(ticket, ticket_reopen_form.cleaned_data['message'])
            return redirect('agent-view-ticket', ticket.id)
    else:
        ticket_reopen_form = forms.TicketReopenForm()

    return render(request, "support/admin/reopen_ticket.html", {
        "ticket": ticket,
        "ticket_reopen_form": ticket_reopen_form
    })
