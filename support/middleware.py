import django.shortcuts
import django.urls
from django.contrib.auth.signals import user_logged_out
from django.dispatch import receiver


@receiver(user_logged_out)
def post_logout(request, **_kwargs):
    request.session["attempted_login"] = False


class TryLogin:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        return response

    def process_view(self, request, callback, _callback_args, _callback_kwargs):
        if getattr(callback, 'try_login_exempt', False):
            return None

        if not request.session.get("attempted_login"):
            request.session["attempted_login"] = True
            return django.shortcuts.redirect(
                django.urls.reverse("oidc_login") + f"?next={request.path}&prompt=none"
            )


def try_login_exempt(view):
    view.try_login_exempt = True
    return view
