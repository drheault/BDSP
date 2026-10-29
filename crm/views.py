from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import ClientForm, ContactForm
from .models import Client, Contact


@login_required
def client_list(request):
    q = request.GET.get("q", "").strip()
    clients = Client.objects.annotate(n_proposals=Count("proposals", distinct=True), n_contacts=Count("contacts", distinct=True))
    if q:
        clients = clients.filter(Q(name__icontains=q) | Q(contacts__name__icontains=q)).distinct()
    template = "crm/_client_rows.html" if request.htmx else "crm/client_list.html"
    return render(request, template, {"clients": clients, "q": q})


@login_required
def client_create(request):
    form = ClientForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        client = form.save()
        messages.success(request, f"Client “{client}” added.")
        return redirect("client_detail", pk=client.pk)
    return render(request, "crm/client_form.html", {"form": form, "title": "New client"})


@login_required
def client_detail(request, pk):
    client = get_object_or_404(Client, pk=pk)
    proposals = client.proposals.select_related("owner").all()
    return render(
        request,
        "crm/client_detail.html",
        {"client": client, "proposals": proposals, "contact_form": ContactForm()},
    )


@login_required
def client_edit(request, pk):
    client = get_object_or_404(Client, pk=pk)
    form = ClientForm(request.POST or None, instance=client)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Client updated.")
        return redirect("client_detail", pk=client.pk)
    return render(request, "crm/client_form.html", {"form": form, "title": f"Edit {client}", "client": client})


@login_required
@require_POST
def client_delete(request, pk):
    client = get_object_or_404(Client, pk=pk)
    if client.proposals.exists():
        messages.error(request, "Cannot delete a client that has proposals.")
        return redirect("client_detail", pk=pk)
    client.delete()
    messages.success(request, "Client deleted.")
    return redirect("client_list")


# ---- contacts (htmx) ----------------------------------------------------------
@login_required
@require_POST
def contact_add(request, client_pk):
    client = get_object_or_404(Client, pk=client_pk)
    form = ContactForm(request.POST)
    if form.is_valid():
        contact = form.save(commit=False)
        contact.client = client
        contact.save()
        return render(
            request,
            "crm/_contact_list.html",
            {"client": client, "contact_form": ContactForm()},
        )
    return render(request, "crm/_contact_list.html", {"client": client, "contact_form": form}, status=422)


@login_required
def contact_edit(request, pk):
    contact = get_object_or_404(Contact, pk=pk)
    if request.method == "POST":
        form = ContactForm(request.POST, instance=contact)
        if form.is_valid():
            form.save()
            return render(request, "crm/_contact_row.html", {"contact": contact})
    else:
        form = ContactForm(instance=contact)
    return render(request, "crm/_contact_edit.html", {"contact": contact, "form": form})


@login_required
def contact_row(request, pk):
    contact = get_object_or_404(Contact, pk=pk)
    return render(request, "crm/_contact_row.html", {"contact": contact})


@login_required
@require_POST
def contact_delete(request, pk):
    contact = get_object_or_404(Contact, pk=pk)
    contact.delete()
    return HttpResponse("")
