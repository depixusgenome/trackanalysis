import {build_views}    from "core/build_views"
import *        as p    from "core/properties"
import {WidgetView, Widget} from "models/widgets/widget"

export class DpxFitParamsView extends WidgetView
    tagName: "div"

    on_change_frozen: () ->
        $(@el).find('.dpx-pk-freeze').prop('disabled', @model.frozen)

    on_input: (evt) ->
        id = evt.target.id[7...]
        if id == "locksequence"
            elem       = $(@el)
            @model[id] = elem.find("#dpx-pk-locksequence").prop("checked")

            elem = elem.find("#dpx-pk-ls-icon")
            elem.removeClass()
            if @model[id]
                elem.addClass("icon-dpx-lock")
            else
                elem.addClass("icon-dpx-unlocked")
        else
            @model[id] = evt.target.value

    on_change_input: (evt) ->
        itm = $(@el).find("#dpx-pk-#{evt}")
        if "#{evt}" == "locksequence"
            itm.prop("checked", @model.locksequence)
        else
            itm.val("#{@model[evt]}")

    connect_signals: () ->
        super()
        for evt in @cl_inputs
            @connect(@model.properties[evt].change,
                     do (event = evt, me = @) -> (val) -> me.on_change_input(event))
        @connect(@model.properties.frozen.change, () => @on_change_frozen())

    render: () ->
        super()
        dbal  = 'data-balloon="'
        pos   = '" data-balloon-length="medium" data-balloon-pos="right"'
        ttips = [dbal+'Force a stretch value'+pos,
                 dbal+'Force a bias value'+pos,
                 dbal+'Lock the sequence to the currently selected one'+pos]

        html  = "<div class='dpx-span'>"+
                    @mk_inp("stretch", "Stretch (base/µm)", ttips[0])+
                    @mk_inp("bias",    "Bias (µm)", ttips[1])+
                "</div>" + @mk_check(ttips[2])
                

        @el.innerHTML = html

        elem = $(@el)
        for evt in @cl_inputs
            elem.find("#dpx-pk-#{evt}").change((e) => @on_input(e))
        return @

    cl_inputs: ["stretch", "bias", "locksequence"]

    mk_inp: (name, label, ttip) ->
        disabled = if @model.frozen then ' disabled=true' else ''
        return  "<input id='dpx-pk-#{name}' #{ttip}"+
                    " class='dpx-pk-freeze bk-widget-form-input' type='text' "+
                    " placeholder='#{label}' value='#{@model[name]}'#{disabled}>"

    mk_check: (ttip) ->
        disabled = if @model.frozen then ' disabled=true' else ''
        checked  = if @model.locksequence then ' checked=true' else ''
        icon     = if @model.locksequence then 'lock' else 'unlocked'
        return "<div class='bk-bs-btn-group' id='dpx-pk-ls-grp'>"+
                "<label class='bk-bs-btn bk-bs-btn-default dpx-pk-freeze' "+
                    "id='dpx-pk-ls-label' #{disabled}><span id='dpx-pk-ls-icon' "+
                    "class='icon-dpx-#{icon}'></span>"+
                    "<input id='dpx-pk-locksequence' #{ttip}"+
                        " class='dpx-pk-freeze bk-widget-form-input' type='checkbox' "+
                        " #{checked}#{disabled}></input></label></div>"

export class DpxFitParams extends Widget
    default_view: DpxFitParamsView
    type:         "DpxFitParams"

    initialize: (attributes, options) ->
        super(attributes, options)
        @css_classes = ["dpx-params", "dpx-widget"]

    @define {
        frozen:       [p.Bool, true],
        stretch:      [p.String, ""],
        bias:         [p.String, ""],
        locksequence: [p.Bool]
    }
