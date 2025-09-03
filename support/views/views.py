from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_POST
from .. import forms, models, tasks
import requests
import stripe.identity
import pgpy
from django.core.paginator import Paginator
from django.conf import settings
from django.db.models import Max
from django.contrib.auth.decorators import login_required
from django.core.exceptions import SuspiciousOperation


def index(request):
    return render(request, "support/index.html")


def new_ticket(request):
    if request.method == "POST":
        form = forms.TicketForm(request.POST)
    else:
        form = forms.TicketForm()

    if request.user.is_authenticated:
        form.fields['name'].initial = request.user.customer.full_name
        form.fields['name'].disabled = True
        form.fields['email'].initial = request.user.customer.email
        form.fields['email'].disabled = True
        form.fields['phone'].initial = request.user.customer.phone
        form.fields['phone'].disabled = True
        form.fields['phone_ext'].value = request.user.customer.phone_ext
        form.fields['phone_ext'].disabled = True

    if request.method == "POST":
        if request.user.is_authenticated:
            recaptcha_success = True
        else:
            recaptcha_success = False
            recaptcha_resp = request.POST.get("g-recaptcha-response")
            if not settings.RECAPTCHA_SECRET_KEY:
                recaptcha_success = True
            else:
                if recaptcha_resp:
                    r = requests.post("https://www.google.com/recaptcha/api/siteverify", data={
                        "secret": settings.RECAPTCHA_SECRET_KEY,
                        "response": recaptcha_resp
                    }).json()
                    recaptcha_success = r["success"]

        if recaptcha_success and form.is_valid():
            if request.user.is_authenticated:
                customer = request.user.customer
            else:
                is_valid = True
                customer = models.Customer.objects.filter(email=form.cleaned_data['email']).first()
                if customer:
                    if customer.user and customer.user != request.user:
                        is_valid = False
                        form.add_error('email', "Email already connected to user, please login.")
                else:
                    customer = models.Customer(
                        email=form.cleaned_data['email'],
                    )

                if is_valid:
                    customer.full_name = form.cleaned_data['name']
                    customer.phone = form.cleaned_data['phone']
                    customer.phone_ext = form.cleaned_data['phone_ext']
                    customer.save()

            tasks.open_ticket(
                customer, form.cleaned_data['subject'], form.cleaned_data['message'], models.Ticket.SOURCE_WEB,
                models.Ticket.PRIORITY_NORMAL, verified=request.user.is_authenticated
            )
            return render(request, "support/ticket_opened.html", {
                "ticket_email": customer.email
            })

    return render(request, "support/new_ticket.html", {
        "ticket_form": form
    })


@login_required
def tickets(request):
    user_tickets = models.Ticket.objects.annotate(latest_message=Max('messages__date')) \
        .order_by('-latest_message') \
        .filter(customer=request.user.customer) \
        .distinct()

    tickets = Paginator(user_tickets, 10)

    page_number = request.GET.get('page')
    page_obj = tickets.get_page(page_number)

    return render(request, "support/tickets.html", {
        "tickets": page_obj
    })


@login_required
def ticket(request, ticket_id):
    user_ticket = get_object_or_404(models.Ticket, id=ticket_id)

    if user_ticket.customer != request.user.customer:
        raise SuspiciousOperation()

    if request.method == "POST":
        ticket_reply_form = forms.TicketCustomerReplyForm(request.POST)
        if ticket_reply_form.is_valid() and user_ticket.state != user_ticket.STATE_CLOSED:
            tasks.post_message(user_ticket, ticket_reply_form.cleaned_data['message'])
            return redirect('view-ticket', user_ticket.id)
    else:
        ticket_reply_form = forms.TicketCustomerReplyForm()

    return render(request, "support/ticket.html", {
        "ticket": user_ticket,
        "ticket_reply_form": ticket_reply_form
    })


@login_required
def verify_ticket(request, verification_token):
    user_ticket = get_object_or_404(models.Ticket, verification_token=verification_token)

    user_ticket.customer = request.user.customer
    user_ticket.customer_verified = True
    user_ticket.save()

    return render(request, "support/ticket_verified.html")


@login_required
def verify_ticket_alt(request, ticket_id):
    user_ticket = get_object_or_404(models.Ticket, id=ticket_id)

    if user_ticket.customer != request.user.customer:
        raise SuspiciousOperation()

    if request.method == "POST" and request.POST.get("verify") == "true":
        user_ticket.customer = request.user.customer
        user_ticket.customer_verified = True
        user_ticket.save()
        return redirect('view-ticket', user_ticket.id)

    return render(request, "support/verify_ticket.html", {
        "ticket": user_ticket
    })


def do_kyc(request, session_id):
    verification_session = get_object_or_404(models.VerificationSession, id=session_id)

    stripe_verification_session = stripe.identity.VerificationSession.retrieve(verification_session.stripe_session)

    return redirect(stripe_verification_session.url)


@login_required
def pgp_keys(request):
    keys = models.CustomerPGPKey.objects.filter(customer=request.user.customer)

    return render(request, "support/pgp_keys.html", {
        "keys": keys
    })


@login_required
def new_pgp_key(request):
    if request.method == "POST":
        form = forms.PGPKeyForm(request.POST)
        if form.is_valid():
            try:
                key, _ = pgpy.PGPKey.from_blob(form.cleaned_data['key'])
            except (ValueError, pgpy.errors.PGPError):
                form.add_error('key', "No valid PGP key found")
            else:
                models.CustomerPGPKey.objects.update_or_create(
                    customer=request.user.customer,
                    fingerprint=key.fingerprint,
                    defaults={
                        "pgp_key": str(key),
                        "primary": request.user.customer.pgp_keys.count() == 0,
                    }
                )
                return redirect('pgp_keys')
    else:
        form = forms.PGPKeyForm()

    return render(request, "support/add_pgp_key.html", {
        "form": form
    })


@login_required
@require_POST
def make_pgp_key_primary(request, key_id):
    key = get_object_or_404(models.CustomerPGPKey, id=key_id)
    if request.POST.get("make_pgp_key_primary") == "true" and key.customer == request.user.customer:
        models.CustomerPGPKey.objects.all().update(primary=False)
        key.primary = True
        key.save()

    return redirect('pgp_keys')
