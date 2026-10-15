frappe.ui.form.on("Item Type", {
    refresh(frm) {
        if (!frm.is_new() && !frm.doc.disabled) {
            frm.add_custom_button(__("Create Item of this Type"), () => {
                frappe.route_options = { item_type: frm.doc.name };
                frappe.set_route("item-creator");
            });
        }
        frm.set_intro(
            __("[ ] marks optional parts. Empty parts are skipped in the final name. A type already used by items cannot be deleted - tick Disabled instead."),
            "blue"
        );
    },
});
