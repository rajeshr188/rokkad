from django.urls import include, path

from . import views

urlpatterns = (
    # urls for Django Rest Framework API
    path("", views.home, name="product_product_home"),
)

urlpatterns += (
    # urls for Category
    path("category/", views.category_list, name="product_category_list"),
    path(
        "category/create/",
        views.category_create,
        name="product_category_create",
    ),
    path(
        "category/detail/<slug:slug>/",
        views.category_detail,
        name="product_category_detail",
    ),
    path(
        "category/update/<slug:slug>/",
        views.category_update,
        name="product_category_update",
    ),
)

urlpatterns += (
    # urls for ProductType
    path(
        "producttype/",
        views.producttype_list,
        name="product_producttype_list",
    ),
    path(
        "producttype/create/",
        views.producttype_create,
        name="product_producttype_create",
    ),
    path(
        "producttype/<int:pk>/detail/",
        views.producttype_detail,
        name="product_producttype_detail",
    ),
    path(
        "producttype/<int:pk>/update//",
        views.producttype_update,
        name="product_producttype_update",
    ),
    path(
        "producttype/<int:pk>/delete/",
        views.producttype_delete,
        name="product_producttype_delete",
    ),
    path(
        "producttype/<int:product_type_id>/generate/",
        views.generate_products_and_variants,
        name="generate_products",
    ),
)

urlpatterns += (
    # urls for Product
    path("product/", views.product_list, name="product_product_list"),
    path(
        "producttype/<int:type_pk>/product/create",
        views.product_create,
        name="product_product_create",
    ),
    path(
        "product/<int:pk>/detail/",
        views.product_detail,
        name="product_product_detail",
    ),
    path("product/<int:pk>/update/", views.product_edit, name="product_product_update"),
    path(
        "product/<int:pk>/delete/",
        views.ProductDeleteView.as_view(),
        name="product_product_delete",
    ),
)

urlpatterns += (
    # urls for ProductVariant
    path(
        "productvariant/",
        views.productvariant_list,
        name="product_productvariant_list",
    ),
    path(
        "product/<int:pk>/variant/create/",
        views.variant_create,
        name="product_productvariant_create",
    ),
    path(
        "productvariant/<int:pk>/detail/",
        views.productvariant_detail,
        name="product_productvariant_detail",
    ),
    path(
        "productvariant/<int:pk>/update/",
        views.productvariant_update,
        name="product_productvariant_update",
    ),
    path(
        "productvariant/<int:pk>/delete/",
        views.ProductVariantDeleteView.as_view(),
        name="product_productvariant_delete",
    ),
)

urlpatterns += (
    # urls for Attribute
    path(
        "attribute/", views.AttributeListView.as_view(), name="product_attribute_list"
    ),
    path(
        "attribute/create/",
        views.AttributeCreateView.as_view(),
        name="product_attribute_create",
    ),
    path(
        "attribute/<slug:slug>/detail/",
        views.AttributeDetailView.as_view(),
        name="product_attribute_detail",
    ),
    path(
        "attribute/<slug:slug>/update/",
        views.AttributeUpdateView.as_view(),
        name="product_attribute_update",
    ),
)

urlpatterns += (
    # urls for AttributeValue
    path(
        "attributevalue/",
        views.AttributeValueListView.as_view(),
        name="product_attributevalue_list",
    ),
    path(
        "attributevalue/create/",
        views.AttributeValueCreateView.as_view(),
        name="product_attributevalue_create",
    ),
    path(
        "attributevalue/<slug:slug>/detail/",
        views.AttributeValueDetailView.as_view(),
        name="product_attributevalue_detail",
    ),
    path(
        "attributevalue/<slug:slug>/update/",
        views.AttributeValueUpdateView.as_view(),
        name="product_attributevalue_update",
    ),
)

urlpatterns += (
    # urls for ProductImage
    path(
        "productimage/",
        views.ProductImageListView.as_view(),
        name="product_productimage_list",
    ),
    path(
        "productimage/create/",
        views.ProductImageCreateView.as_view(),
        name="product_productimage_create",
    ),
    path(
        "productimage/detail/<int:pk>/",
        views.ProductImageDetailView.as_view(),
        name="product_productimage_detail",
    ),
    path(
        "productimage/update/<int:pk>/",
        views.ProductImageUpdateView.as_view(),
        name="product_productimage_update",
    ),
)

urlpatterns += (
    # urls for VariantImage
    path(
        "variantimage/",
        views.VariantImageListView.as_view(),
        name="product_variantimage_list",
    ),
    path(
        "variantimage/create/",
        views.VariantImageCreateView.as_view(),
        name="product_variantimage_create",
    ),
    path(
        "variantimage/detail/<int:pk>/",
        views.VariantImageDetailView.as_view(),
        name="product_variantimage_detail",
    ),
    path(
        "variantimage/update/<int:pk>/",
        views.VariantImageUpdateView.as_view(),
        name="product_variantimage_update",
    ),
)

urlpatterns += (
    # urls for Stock
    path("stock/", views.stock_list, name="product_stock_list"),
    # path("stock/create/", views.StockCreateView.as_view(), name="product_stock_create"),
    path(
        "stock/detail/<int:pk>/",
        views.StockDetailView.as_view(),
        name="product_stock_detail",
    ),
    path("stock/<int:pk>/delete/", views.stock_delete, name="product_stock_delete"),
    path("stock/<int:pk>/split/", views.split_lot, name="product_stock_split"),
    path("stock/merge/<int:pk>", views.merge_lot, name="product_stock_merge"),
    path("stock/audit/", views.audit_stock, name="product_stock_audit"),
    path("stock/search/", views.stock_select, name="stock_select"),
    path("stock/create/", views.stockin_journalentry, name="stock_in_journalentry"),
    path("stock/transaction/", views.stockout_journalentry, name="stock_journalentry"),
    path(
        "stock/transaction/<int:pk>/",
        views.stockout_journalentry,
        name="stock_journalentry",
    ),
)
urlpatterns += (
    # urls for Stocktransaction
    path(
        "stocktransaction/",
        views.StockTransactionListView.as_view(),
        name="product_stocktransaction_list",
    ),
)
urlpatterns += (
    path(
        "stockstatement/",
        views.StockStatementListView.as_view(),
        name="product_stockstatement_list",
    ),
    path(
        "stockstatment/add_physical/",
        views.StockStatementView.as_view(),
        name="product_stockstatement_add",
    ),
)
urlpatterns += (
    path("pricingtier/", views.pricing_tier_list, name="product_pricingtier_list"),
    path(
        "pricingtier/<int:pk>/",
        views.pricing_tier_detail,
        name="product_pricingtier_detail",
    ),
    path(
        "pricingtier/create/",
        views.pricing_tier_create,
        name="product_pricingtier_create",
    ),
    path(
        "pricingtier/<int:pk>/update",
        views.pricing_tier_update,
        name="product_pricingtier_update",
    ),
    path(
        "pricingtier/<int:pk>/delete/",
        views.pricing_tier_delete,
        name="product_pricingtier_delete",
    ),
    path(
        "pricingtier/<int:pk>/addproductprice",
        views.pricing_tier_product_price_create,
        name="product_pricingtier_productprice_create",
    ),
    path(
        "pricingtier/productprice/<int:pk>/update",
        views.pricing_tier_product_price_update,
        name="product_pricingtier_productprice_update",
    ),
    path(
        "pricingtier/productprice/<int:pk>/delete",
        views.pricing_tier_product_price_delete,
        name="product_pricingtier_productprice_delete",
    ),
)
