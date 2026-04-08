# class Render:
#     @staticmethod
#     def render(path: str, params: dict):
#         template = get_template(path)
#         html = template.render(params)
#         response = BytesIO()
#         pdf = pisa.pisaDocument(BytesIO(html.encode("UTF-8")), response)
#         if not pdf.err:
#             return HttpResponse(response.getvalue(), content_type="application/pdf")
#         else:
#             return HttpResponse("Error Rendering PDF", status=400)
