app_name = "exeliq_items"
app_title = "Exeliq Items"
app_publisher = "Exeliq Tech Solutions Pvt. Ltd."
app_description = "Structured Item name creation with duplicate checks"
app_email = "admin@exeliq.com"
app_license = "mit"
required_apps = ["erpnext"]

# Custom fields on Item + one-time seeding of Item Types and code series.
# Both are idempotent, so running them on every migrate is safe.
after_install = "exeliq_items.setup.install.after_install"
after_migrate = "exeliq_items.setup.install.after_migrate"

doctype_list_js = {"Item": "public/js/item_list.js"}
