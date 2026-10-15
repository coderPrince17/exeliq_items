// Item Creator - builds "Type - Make/Model/P1/P2/P3" names, checks for duplicates, creates the Item.
const EXL_API = "exeliq_items.api.";

frappe.pages["item-creator"].on_page_load = function (wrapper) {
    const page = frappe.ui.make_app_page({
        parent: wrapper,
        title: __("New Item"),
        single_column: true,
    });
    wrapper.item_creator = new ExlItemCreator(page);
};

frappe.pages["item-creator"].on_page_show = function (wrapper) {
    const ic = wrapper.item_creator;
    if (!ic) return;
    const opts = frappe.route_options;
    frappe.route_options = null;
    if (opts && opts.item_type) {
        ic.ready.then(() => ic.controls.item_type.set_value(opts.item_type));
    }
};

class ExlItemCreator {
    constructor(page) {
        this.page = page;
        this.controls = {};
        this.param_controls = [];
        this.type = null;
        this.result = null;
        this.seq = 0;
        this.boot = {};
        this.add_style();
        this.make_layout();
        this.make_actions();
        this.ready = frappe
            .call(EXL_API + "get_bootstrap")
            .then((r) => {
                this.boot = r.message || {};
                this.make_controls();
                this.render_result();
                if (this.boot.naming_by_series) {
                    this.$notice.html(
                        `<div class="exl-alert exl-alert-red">${__(
                            "Stock Settings → Item Naming By is set to Naming Series. ERPNext will replace the item code this page assigns. Switch it to Item Code."
                        )}</div>`
                    );
                }
            });
    }

    // ------------------------------------------------------------ layout

    add_style() {
        if (document.getElementById("exl-ic-style")) return;
        const css = `
        .exl-ic { display:grid; grid-template-columns: minmax(0,1.4fr) minmax(0,1fr); gap:20px; padding:4px 0 40px; }
        @media (max-width: 991px) { .exl-ic { grid-template-columns: 1fr; } }
        .exl-card { background: var(--card-bg); border:1px solid var(--border-color); border-radius: var(--border-radius-lg); padding:16px 20px; margin-bottom:16px; }
        .exl-step { font-size: var(--text-xs); font-weight:600; letter-spacing:.06em; text-transform:uppercase; color: var(--text-muted); margin-bottom:10px; }
        .exl-format { font-size: var(--text-sm); color: var(--text-muted); margin:-4px 0 10px; font-family: var(--font-stack-monospace, monospace); }
        .exl-params { display:grid; grid-template-columns: 1fr 1fr; gap:0 16px; }
        @media (max-width: 575px) { .exl-params { grid-template-columns: 1fr; } }
        .exl-side { position: sticky; top: 70px; align-self:start; }
        .exl-name { font-size: 1.25rem; font-weight:600; color: var(--heading-color); word-break: break-word; line-height:1.4; min-height: 1.75rem; }
        .exl-name.empty { color: var(--text-light); font-weight:400; font-size: var(--text-base); }
        .exl-meta { display:flex; gap:12px; flex-wrap:wrap; margin-top:8px; font-size: var(--text-sm); color: var(--text-muted); }
        .exl-badge { display:inline-block; padding:2px 10px; border-radius:999px; font-size: var(--text-xs); font-weight:600; }
        .exl-badge.ok { background: var(--green-100); color: var(--green-700); }
        .exl-badge.warn { background: var(--yellow-100); color: var(--yellow-800, #8a6d00); }
        .exl-badge.bad { background: var(--red-100); color: var(--red-700); }
        .exl-list { list-style:none; padding:0; margin:8px 0 0; }
        .exl-list li { padding:8px 0; border-top:1px solid var(--border-color); font-size: var(--text-sm); }
        .exl-list li:first-child { border-top:none; }
        .exl-list .why { color: var(--text-muted); font-size: var(--text-xs); }
        .exl-list .dis { color: var(--text-light); font-size: var(--text-xs); margin-left:6px; }
        .exl-alert { padding:10px 12px; border-radius: var(--border-radius); font-size: var(--text-sm); margin-bottom:12px; }
        .exl-alert-red { background: var(--red-50, #fff5f5); color: var(--red-700); border:1px solid var(--red-200, #fdd); }
        .exl-h { font-weight:600; font-size: var(--text-sm); margin-top:14px; }
        .exl-h.red { color: var(--red-600); } .exl-h.yellow { color: var(--yellow-700, #8a6d00); }
        .exl-errors { margin:8px 0 0; padding-left:18px; font-size: var(--text-sm); color: var(--red-600); }
        .exl-create { width:100%; margin-top:16px; }
        .exl-hint { font-size: var(--text-xs); color: var(--text-muted); margin-top:8px; }
        `;
        $(`<style id="exl-ic-style">${css}</style>`).appendTo("head");
    }

    make_layout() {
        const $main = $(this.page.main);
        $main.empty();
        this.$notice = $(`<div></div>`).appendTo($main);
        const $grid = $(`<div class="exl-ic"></div>`).appendTo($main);
        const $left = $(`<div></div>`).appendTo($grid);
        const $right = $(`<div class="exl-side"></div>`).appendTo($grid);

        this.$step1 = $(`<div class="exl-card"><div class="exl-step">${__("1 · What is it?")}</div></div>`).appendTo($left);
        this.$step2 = $(`<div class="exl-card"><div class="exl-step">${__("2 · Identify it")}</div>
            <div class="exl-format"></div><div class="exl-ident"></div><div class="exl-params"></div></div>`).appendTo($left);
        this.$step3 = $(`<div class="exl-card"><div class="exl-step">${__("3 · Item details")}</div>
            <div class="exl-params exl-details"></div></div>`).appendTo($left);
        this.$result = $(`<div class="exl-card"></div>`).appendTo($right);

        this.$format = this.$step2.find(".exl-format");
        this.$ident = this.$step2.find(".exl-ident");
        this.$params = this.$step2.find(".exl-params");
        this.$details = this.$step3.find(".exl-details");
        this.$step2.hide();
    }

    make_actions() {
        this.page.set_secondary_action(__("Clear"), () => this.reset(true));
        this.page.add_inner_button(__("Manage Item Types"), () => frappe.set_route("List", "Item Type"));
        this.page.add_inner_button(__("New Item Type"), () => frappe.new_doc("Item Type"));
        this.page.add_inner_button(__("Settings"), () => frappe.set_route("Form", "Exeliq Item Settings"));
    }

    // ------------------------------------------------------------ controls

    control(df, $parent) {
        const c = frappe.ui.form.make_control({ df, parent: $parent, render_input: true });
        c.refresh();
        return c;
    }

    make_controls() {
        const me = this;
        const changed = () => me.schedule_preview();

        this.controls.item_type = this.control(
            {
                fieldtype: "Link", fieldname: "item_type", label: __("Item Type"), options: "Item Type", reqd: 1,
                get_query: () => ({ filters: { disabled: 0 } }),
                description: __("Not in the list? Use <b>Other</b>, or click <b>New Item Type</b> above."),
                change: () => me.on_type_change(),
            },
            this.$step1
        );
        this.controls.type_name = this.control(
            {
                fieldtype: "Data", fieldname: "type_name", label: __("Type Name"), reqd: 1,
                description: __("What the item is, e.g. Oscilloscope. Pick an existing spelling if one is suggested."),
                change: changed,
            },
            this.$step1
        );
        this.attach_suggest(this.controls.type_name, () => ({ field: "type_name" }));
        $(this.controls.type_name.wrapper).hide();

        this.controls.brand = this.control(
            {
                fieldtype: "Link", fieldname: "brand", label: __("Make (Brand)"), options: "Brand",
                change: changed,
            },
            this.$ident
        );
        this.controls.model = this.control(
            {
                fieldtype: "Data", fieldname: "model", label: __("Model / Part No."),
                description: __("Exactly as printed by the maker - this is the strongest duplicate check."),
                change: changed,
            },
            this.$ident
        );
        this.attach_suggest(this.controls.model, () => ({ field: "model" }));

        // details
        const groups = this.boot.groups || [];
        this.controls.item_group = this.control(
            {
                fieldtype: "Select", fieldname: "item_group", label: __("Item Group"), reqd: 1,
                options: [""].concat(groups).join("\n"), change: changed,
            },
            this.$details
        );
        this.controls.stock_uom = this.control(
            { fieldtype: "Link", fieldname: "stock_uom", label: __("UOM"), options: "UOM", reqd: 1, default: "Nos" },
            this.$details
        );
        this.controls.stock_uom.set_value("Nos");
        if (this.boot.hsn_field) {
            this.controls.hsn = this.control(
                { fieldtype: "Link", fieldname: "hsn", label: __("HSN/SAC"), options: "GST HSN Code", reqd: 1 },
                this.$details
            );
        }
        this.controls.item_tax_template = this.control(
            { fieldtype: "Link", fieldname: "item_tax_template", label: __("Item Tax Template"), options: "Item Tax Template" },
            this.$details
        );
        this.controls.valuation_rate = this.control(
            { fieldtype: "Currency", fieldname: "valuation_rate", label: __("Valuation Rate") },
            this.$details
        );
        this.controls.is_stock_item = this.control(
            { fieldtype: "Check", fieldname: "is_stock_item", label: __("Maintain Stock"), default: 1 },
            this.$details
        );
        this.controls.is_stock_item.set_value(1);
        this.controls.is_fixed_asset = this.control(
            {
                fieldtype: "Check", fieldname: "is_fixed_asset", label: __("Is Fixed Asset"),
                change: () => {
                    const fa = me.controls.is_fixed_asset.get_value();
                    $(me.controls.asset_category.wrapper).toggle(!!fa);
                    if (fa) me.controls.is_stock_item.set_value(0);
                },
            },
            this.$details
        );
        this.controls.asset_category = this.control(
            { fieldtype: "Link", fieldname: "asset_category", label: __("Asset Category"), options: "Asset Category" },
            this.$details
        );
        $(this.controls.asset_category.wrapper).hide();
        this.controls.description = this.control(
            { fieldtype: "Small Text", fieldname: "description", label: __("Description"),
              description: __("Leave blank to use the item name") },
            this.$details
        );

        // live preview while typing (change only fires on blur)
        ["brand", "model", "type_name"].forEach((f) => this.bind_typing(this.controls[f]));
    }

    bind_typing(ctrl) {
        if (!ctrl || !ctrl.$input) return;
        ctrl.$input.on("input", () => this.schedule_preview());
    }

    // Native <datalist> suggestions: free text stays allowed, values used before show up as you type.
    attach_suggest(ctrl, args_fn) {
        if (!ctrl || !ctrl.$input) return;
        const id = "exl-dl-" + Math.random().toString(36).slice(2, 9);
        const $dl = $(`<datalist id="${id}"></datalist>`).appendTo(ctrl.$wrapper || $(ctrl.wrapper));
        ctrl.$input.attr("list", id).attr("autocomplete", "off");
        let timer = null;
        let last = null;
        const fetch = () => {
            const txt = ctrl.$input.val() || "";
            const args = Object.assign(
                {
                    item_type: this.controls.item_type ? this.controls.item_type.get_value() : null,
                    type_name: this.controls.type_name ? this.controls.type_name.$input.val() : null,
                    txt,
                },
                args_fn()
            );
            const key = JSON.stringify(args);
            if (key === last) return;
            last = key;
            frappe.call({ method: EXL_API + "get_suggestions", args, freeze: false }).then((r) => {
                const vals = r.message || [];
                $dl.empty();
                vals.forEach((v) => $("<option>").attr("value", v).appendTo($dl));
            });
        };
        ctrl.$input.on("input focus", () => {
            clearTimeout(timer);
            timer = setTimeout(fetch, 250);
        });
    }

    // ------------------------------------------------------------ type handling

    on_type_change() {
        const item_type = this.controls.item_type.get_value();
        if (!item_type) {
            this.type = null;
            this.$step2.hide();
            $(this.controls.type_name.wrapper).hide();
            this.schedule_preview();
            return;
        }
        frappe.call({ method: EXL_API + "get_type", args: { item_type } }).then((r) => {
            this.type = r.message;
            this.render_type();
            this.schedule_preview();
        });
    }

    render_type() {
        const t = this.type;
        $(this.controls.type_name.wrapper).toggle(!!t.ask_type_name);

        this.controls.brand.df.reqd = t.make_required ? 1 : 0;
        this.controls.brand.df.description = t.make_required
            ? __("Required for this type")
            : __("Optional - leave blank or GENERIC if there is no make; it is then left out of the name");
        this.controls.brand.refresh();

        $(this.controls.model.wrapper).toggle(t.model_mode !== "No");
        this.controls.model.df.reqd = t.model_mode === "Required" ? 1 : 0;
        this.controls.model.refresh();
        if (t.model_mode === "No") this.controls.model.set_value("");

        this.$format.text(t.format_preview || "");

        // rebuild parameter fields (keep values where the label matches)
        const old = {};
        this.param_controls.forEach((p) => (old[p.label.toLowerCase()] = p.ctrl.get_value()));
        this.$params.empty();
        this.param_controls = [];
        (t.parameters || []).forEach((p) => {
            const $cell = $("<div></div>").appendTo(this.$params);
            const ctrl = this.control(
                {
                    fieldtype: "Data",
                    fieldname: "p_" + this.param_controls.length,
                    label: p.label + (p.suffix ? ` (${p.suffix})` : ""),
                    reqd: p.mandatory ? 1 : 0,
                    change: () => this.schedule_preview(),
                },
                $cell
            );
            if (old[p.label.toLowerCase()]) ctrl.set_value(old[p.label.toLowerCase()]);
            this.bind_typing(ctrl);
            this.attach_suggest(ctrl, () => ({ field: "param", parameter: p.label }));
            this.param_controls.push({ label: p.label, ctrl });
        });

        if (t.default_item_group && (this.boot.groups || []).includes(t.default_item_group)
            && !this.controls.item_group.get_value()) {
            this.controls.item_group.set_value(t.default_item_group);
        }
        if (t.default_uom) this.controls.stock_uom.set_value(t.default_uom);
        this.$step2.show();
    }

    // ------------------------------------------------------------ values / preview

    val(name) {
        const c = this.controls[name];
        if (!c) return null;
        // read the raw input for text fields so the preview follows typing, not just blur
        if (c.$input && ["Data", "Link"].includes(c.df.fieldtype)) return c.$input.val();
        return c.get_value();
    }

    get_values() {
        return {
            item_type: this.controls.item_type.get_value(),
            type_name: this.val("type_name"),
            brand: this.val("brand"),
            model: this.val("model"),
            params: this.param_controls.map((p) => ({ label: p.label, value: p.ctrl.$input ? p.ctrl.$input.val() : p.ctrl.get_value() })),
            item_group: this.controls.item_group.get_value(),
            stock_uom: this.controls.stock_uom.get_value(),
            hsn: this.controls.hsn ? this.controls.hsn.get_value() : null,
            item_tax_template: this.controls.item_tax_template.get_value(),
            valuation_rate: this.controls.valuation_rate.get_value(),
            is_stock_item: this.controls.is_stock_item.get_value(),
            is_fixed_asset: this.controls.is_fixed_asset.get_value(),
            asset_category: this.controls.asset_category.get_value(),
            description: this.controls.description.get_value(),
        };
    }

    schedule_preview() {
        clearTimeout(this._pt);
        this._pt = setTimeout(() => this.run_preview(), 350);
    }

    run_preview() {
        const values = this.get_values();
        if (!values.item_type) {
            this.result = null;
            this.render_result();
            return;
        }
        const seq = ++this.seq;
        this.$result.find(".exl-badge").text(__("Checking…"));
        frappe.call({ method: EXL_API + "preview", args: { data: values }, freeze: false }).then((r) => {
            if (seq !== this.seq) return; // a newer check is already running
            this.result = r.message;
            this.render_result();
        });
    }

    // ------------------------------------------------------------ result panel

    render_result() {
        const esc = frappe.utils.escape_html;
        const r = this.result;
        let html = `<div class="exl-step">${__("Item name")}</div>`;
        if (!r || !r.item_name) {
            html += `<div class="exl-name empty">${__("Pick an Item Type to start")}</div>`;
            this.$result.html(html);
            return;
        }
        const errors = r.errors || [];
        const blocks = r.blocks || [];
        const warns = r.warnings || [];
        let badge = `<span class="exl-badge ok">${__("Ready to create")}</span>`;
        if (errors.length) badge = `<span class="exl-badge bad">${__("Incomplete")}</span>`;
        else if (blocks.length) badge = `<span class="exl-badge bad">${__("Already exists")}</span>`;
        else if (warns.length) badge = `<span class="exl-badge warn">${__("Check similar items")}</span>`;

        html += `<div class="exl-name">${esc(r.item_name)}</div>
            <div class="exl-meta">${badge}
            <span>${r.item_name.length}/140</span>
            ${r.next_code ? `<span>${__("Code")}: <b>${esc(r.next_code)}</b></span>` : ""}</div>`;

        if (errors.length) {
            html += `<ul class="exl-errors">${errors.map((e) => `<li>${esc(e)}</li>`).join("")}</ul>`;
        }
        const item_li = (x) => `<li>
            <a href="/app/item/${encodeURIComponent(x.item_code)}" target="_blank">${esc(x.item_code)}</a>
            ${x.disabled ? `<span class="dis">${__("disabled")}</span>` : ""}<br>
            ${esc(x.item_name || "")}<br><span class="why">${esc(x.reason)}</span></li>`;
        if (blocks.length) {
            html += `<div class="exl-h red">${__("Duplicate - use this item instead")}</div>
                <ul class="exl-list">${blocks.map(item_li).join("")}</ul>`;
        }
        if (warns.length) {
            html += `<div class="exl-h yellow">${__("Similar items - make sure yours is different")}</div>
                <ul class="exl-list">${warns.map(item_li).join("")}</ul>`;
        }
        const can = this.boot.can_create && !errors.length && !blocks.length;
        html += `<button class="btn btn-primary exl-create" ${can ? "" : "disabled"}>
            ${warns.length ? __("Create Anyway…") : __("Create Item")}</button>`;
        if (!this.boot.can_create) html += `<div class="exl-hint">${__("You don't have permission to create Items.")}</div>`;
        else if (blocks.length) html += `<div class="exl-hint">${__("Blocked: an item with this name or model exists. If it is wrong, ask to have it disabled or corrected.")}</div>`;

        this.$result.html(html);
        this.$result.find(".exl-create").on("click", () => this.create());
    }

    // ------------------------------------------------------------ create

    create() {
        const r = this.result;
        if (!r || (r.errors || []).length || (r.blocks || []).length) return;
        const missing = [];
        const v = this.get_values();
        if (!v.item_group) missing.push(__("Item Group"));
        if (!v.stock_uom) missing.push(__("UOM"));
        if (this.controls.hsn && !v.hsn) missing.push(__("HSN/SAC"));
        if (v.is_fixed_asset && !v.asset_category) missing.push(__("Asset Category"));
        if (missing.length) {
            frappe.msgprint({ title: __("Fill item details"), message: missing.join(", "), indicator: "orange" });
            return;
        }
        if ((r.warnings || []).length) {
            frappe.prompt(
                { fieldtype: "Small Text", fieldname: "reason", label: __("Why is this different from the similar items?"), reqd: 1 },
                (d) => this.do_create(v, d.reason),
                __("Create Anyway"),
                __("Create")
            );
        } else {
            this.do_create(v, null);
        }
    }

    do_create(values, reason) {
        frappe.call({
            method: EXL_API + "create_item",
            args: { data: values, override_reason: reason },
            freeze: true,
            freeze_message: __("Creating item…"),
        }).then((res) => {
            const m = res.message;
            if (!m) return;
            frappe.show_alert({ message: __("Created {0}", [m.item_code]), indicator: "green" }, 6);
            const d = new frappe.ui.Dialog({
                title: __("Item created"),
                fields: [{ fieldtype: "HTML", fieldname: "msg" }],
                primary_action_label: __("Create Another"),
                primary_action: () => { d.hide(); this.reset(false); },
                secondary_action_label: __("Open Item"),
                secondary_action: () => { d.hide(); frappe.set_route("Form", "Item", m.item_code); },
            });
            d.fields_dict.msg.$wrapper.html(
                `<p><b>${frappe.utils.escape_html(m.item_code)}</b></p><p>${frappe.utils.escape_html(m.item_name)}</p>`
            );
            d.show();
        });
    }

    // full=true clears everything; false keeps type and group so similar items are quick to add
    reset(full) {
        const keep = full ? {} : {
            item_type: this.controls.item_type.get_value(),
            item_group: this.controls.item_group.get_value(),
            stock_uom: this.controls.stock_uom.get_value(),
            hsn: this.controls.hsn ? this.controls.hsn.get_value() : null,
            item_tax_template: this.controls.item_tax_template.get_value(),
            brand: this.controls.brand.get_value(),
            type_name: this.controls.type_name.get_value(),
        };
        ["type_name", "brand", "model", "valuation_rate", "description", "asset_category"].forEach((f) =>
            this.controls[f] && this.controls[f].set_value(keep[f] || "")
        );
        this.param_controls.forEach((p) => p.ctrl.set_value(""));
        this.controls.is_fixed_asset.set_value(0);
        this.controls.is_stock_item.set_value(1);
        if (full) {
            this.controls.item_type.set_value("");
            this.controls.item_group.set_value("");
            this.controls.stock_uom.set_value("Nos");
            if (this.controls.hsn) this.controls.hsn.set_value("");
            this.controls.item_tax_template.set_value("");
        }
        this.result = null;
        this.render_result();
        this.schedule_preview();
    }
}
