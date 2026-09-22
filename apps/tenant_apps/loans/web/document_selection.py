from django.shortcuts import render


def address_selection_response(request, error):
    response = render(request, "loans/setup/documents/address_selection.html", {
        "choices": error.choices, "message": str(error),
        "query": [(key, value) for key, values in request.GET.lists() if key != "address" for value in values],
    }, status=409)
    response["Cache-Control"] = "private, no-store"
    return response
