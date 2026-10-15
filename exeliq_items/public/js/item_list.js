// Adds a "New Item (Structured)" button to the Item list, keeping ERPNext's own list settings.
(function () {
    const settings = (frappe.listview_settings["Item"] = frappe.listview_settings["Item"] || {});
    const prev_onload = settings.onload;
    settings.onload = function (listview) {
        if (prev_onload) prev_onload(listview);
        listview.page.add_inner_button(__("New Item (Structured)"), () => frappe.set_route("item-creator"));
    };
})();
