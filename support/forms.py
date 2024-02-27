import django.contrib.auth.models
from django import forms
import crispy_forms.helper
import crispy_forms.layout
import crispy_forms.bootstrap
from phonenumber_field.formfields import PhoneNumberField
import markdown2
from django.conf import settings
from . import models

markdown = markdown2.Markdown(extras=[
    "fenced-code-blocks", "cuddled-lists", "smarty-pants", "strike", "target-blank-links"
])


class TicketForm(forms.Form):
    name = forms.CharField(label="Your name", required=True, max_length=255)
    email = forms.EmailField(label="Your email", required=True)
    phone = PhoneNumberField(label="Your phone", required=False)
    phone_ext = forms.CharField(label="Phone ext", required=False, max_length=64)
    subject = forms.CharField(label="Subject", required=True, max_length=255)
    message = forms.CharField(
        widget=forms.Textarea(attrs={
            "rows": 5
        }), label="Message", required=True
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.helper = crispy_forms.helper.FormHelper()
        self.helper.use_custom_control = False
        self.helper.field_class = 'my-1'
        self.helper.form_id = "newTicketForm"
        self.helper.layout = crispy_forms.layout.Layout(
            crispy_forms.layout.Fieldset(
                'About you',
                'name',
                'email',
                crispy_forms.layout.Row(
                    crispy_forms.layout.Column('phone'),
                    crispy_forms.layout.Column('phone_ext'),
                )
            ),
            crispy_forms.layout.Fieldset(
                'Your query',
                'subject',
                'message',
            )
        )

        self.helper.add_input(
            crispy_forms.layout.Submit(
                'button', 'Open ticket', css_class='g-recaptcha',
                data_sitekey=settings.RECAPTCHA_SITE_KEY, data_callback='onFormSubmit'
            )
        )

    def clean_message(self):
        data = self.cleaned_data['message']
        return markdown.convert(data)


class TicketReplyForm(forms.Form):
    message = forms.CharField(
        widget=forms.Textarea(attrs={
            "rows": 5
        }), label="Message", required=True
    )
    close = forms.BooleanField(label="Close on reply", required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.helper = crispy_forms.helper.FormHelper()
        self.helper.use_custom_control = False
        self.helper.field_class = 'my-1'
        self.helper.layout = crispy_forms.layout.Layout(
            'message',
            crispy_forms.layout.HTML(
                '<p>'
                'Markdown supported<br/>'
                '<small>Greeting and signature will be added automatically</small>'
                '</p>'
            ),
            'close',
            crispy_forms.layout.Hidden('type', 'ticket_reply')
        )

        self.helper.add_input(crispy_forms.layout.Submit('submit', 'Post reply'))

    def clean_message(self):
        data = self.cleaned_data['message']
        return markdown.convert(data)


class TicketCustomerReplyForm(forms.Form):
    message = forms.CharField(
        widget=forms.Textarea(attrs={
            "rows": 5
        }), label="Message", required=True
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.helper = crispy_forms.helper.FormHelper()
        self.helper.use_custom_control = False
        self.helper.field_class = 'my-1'
        self.helper.layout = crispy_forms.layout.Layout(
            'message',
            crispy_forms.layout.HTML(
                '<p>Styling with Markdown is supported</p>'
            ),
        )

        self.helper.add_input(crispy_forms.layout.Submit('submit', 'Post reply'))

    def clean_message(self):
        data = self.cleaned_data['message']
        return markdown.convert(data)


class TicketNoteForm(forms.Form):
    message = forms.CharField(
        widget=forms.Textarea(attrs={
            "rows": 5
        }), label="Note", required=True
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.helper = crispy_forms.helper.FormHelper()
        self.helper.use_custom_control = False
        self.helper.field_class = 'my-1'
        self.helper.layout = crispy_forms.layout.Layout(
            'message',
            crispy_forms.layout.Hidden('type', 'ticket_note')
        )

        self.helper.add_input(crispy_forms.layout.Submit('submit', 'Post note'))

    def clean_message(self):
        data = self.cleaned_data['message']
        return markdown.convert(data)


class TicketEditForm(forms.ModelForm):
    class Meta:
        model = models.Ticket
        fields = ('source', 'priority', 'due_date', 'subject')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.helper = crispy_forms.helper.FormHelper()
        self.helper.use_custom_control = False
        self.helper.field_class = 'my-1'
        self.helper.layout = crispy_forms.layout.Layout(
            'source',
            'priority',
            'subject',
            'due_date'
        )

        self.helper.add_input(crispy_forms.layout.Submit('submit', 'Update'))


class TicketCloseForm(forms.Form):
    message = forms.CharField(
        widget=forms.Textarea(attrs={
            "rows": 5
        }), label="Note", required=True
    )
    silent = forms.BooleanField(label="Close silently", required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.helper = crispy_forms.helper.FormHelper()
        self.helper.use_custom_control = False
        self.helper.field_class = 'my-1'
        self.helper.layout = crispy_forms.layout.Layout(
            'message',
            'silent',
            crispy_forms.layout.ButtonHolder(
                crispy_forms.layout.HTML(
                    '<a href="{% url "agent-view-ticket" ticket.id %}" class="btn btn-primary">Cancel</a>'),
                crispy_forms.layout.Submit('submit', 'Close ticket', css_class='btn-danger'),
                css_class='btn-group mt-3'
            )
        )

    def clean_message(self):
        data = self.cleaned_data['message']
        return markdown.convert(data)


class TicketReopenForm(forms.Form):
    message = forms.CharField(
        widget=forms.Textarea(attrs={
            "rows": 5
        }), label="Note", required=True
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.helper = crispy_forms.helper.FormHelper()
        self.helper.use_custom_control = False
        self.helper.field_class = 'my-1'
        self.helper.layout = crispy_forms.layout.Layout(
            'message',
            crispy_forms.layout.ButtonHolder(
                crispy_forms.layout.HTML(
                    '<a href="{% url "agent-view-ticket" ticket.id %}" class="btn btn-primary">Cancel</a>'),
                crispy_forms.layout.Submit('submit', 'Reopen ticket', css_class='btn-success'),
                css_class='btn-group mt-3'
            )
        )

    def clean_message(self):
        data = self.cleaned_data['message']
        markdown = markdown2.Markdown()
        return markdown.convert(data)


class UserModelChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return f"{obj.get_full_name()} - {obj.email}"

class TicketAssignForm(forms.Form):
    assign_to = UserModelChoiceField(
        queryset=django.contrib.auth.models.User.objects.filter(
            customer__is_agent=True
        ), label="Assign to", required=True
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.helper = crispy_forms.helper.FormHelper()
        self.helper.use_custom_control = False
        self.helper.field_class = 'my-1'
        self.helper.layout = crispy_forms.layout.Layout(
            'assign_to',
            crispy_forms.layout.ButtonHolder(
                crispy_forms.layout.HTML(
                    '<a href="{% url "agent-view-ticket" ticket.id %}" class="btn btn-primary">Cancel</a>'),
                crispy_forms.layout.Submit('submit', 'Assign ticket', css_class='btn-success'),
                css_class='btn-group mt-3'
            )
        )

