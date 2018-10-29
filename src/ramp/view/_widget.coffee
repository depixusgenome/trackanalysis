import {build_views}    from "core/build_views"
import *        as p    from "core/properties"
import {WidgetView, Widget} from "models/widgets/widget"

export class DpxRampView extends WidgetView
    tagName: "div"

    on_change_frozen: () ->
        $(@el).find('.dpx-rp-freeze').prop('disabled', @model.frozen)

    on_input: (evt) ->
        @model[evt] = Number($(@el).find("#dpx-rp-#{evt}").val())

    on_change_input: (evt) ->
        $(@el).find("#dpx-rp-#{evt}").val("#{@model[evt]}")

    connect_signals: () ->
        super()
        for evt in @cl_inputs
            @connect(@model.properties[evt].change,
                     do (event = evt, me = @) -> (val) -> me.on_change_input(event))
        @connect(@model.properties.displaytype.change,  () => @render())
        @connect(@model.properties.frozen.change, () => @on_change_frozen())

    render: () ->
        super()
        dbal  = 'data-balloon="'
        pos   = '" data-balloon-length="medium" data-balloon-pos="right"'
        ttips = [dbal+'beads with a small range of values are defined as fixed'+pos,
                 dbal+'Beads with a range of values to small or too big are deleted'+pos,
                 dbal+'Constant or noisy beads are deleted'+pos,
                 dbal+'Normalize all bead sizes to 1.'+pos]


        empty = "<br style='margin-top: 16px;'/>"
        html  = "<div><table>"+
                    "<tr><td>#{@mk_inp("minhfsigma", 0.05, 0.0001)}</td>"+
                        "<td #{ttips[2]}>≤ σ[HF] ≤</td>"+
                        "<td>#{@mk_inp("maxhfsigma", 0.05,  0.001)}</td></tr>"+
                    "<tr><td>#{@mk_inp("minextension")}</td>"+
                        "<td #{ttips[1]}>≤ Δz ≤</td>"+
                        "<td>#{@mk_inp("maxextension")}</td></tr>"+
                    "<tr><td></td>"+
                        "<td #{ttips[0]}>Δz fixed ≤</td>"+
                        "<td>#{@mk_inp("fixedextension")}</td></tr>"+
                  "</table></div>"+
                  "<div><table><tr>"

        labels = ["raw data", "Z (% strand size)", "Z (µm)"]
        for j in [0..2]
            html += '<td><label class="bk-bs-radio"><input'
            if j == @model.displaytype
                html += ' checked=true'
            html += " type='radio' id='dpx-rp-displaytype-#{j}' class='dpx-rp-displaytype-itm'/>"+
                    "#{labels[j]}</label></td>"
        html += "</tr></table></div>"

        @el.innerHTML = html
        elem = $(@el)

        for evt in @cl_inputs
            el = elem.find("#dpx-rp-#{evt}")
            el.change((e) => @model[e.target.id[7...]] = Number(e.target.value))

        for i in [0..2]
            elem.find("#dpx-rp-displaytype-#{i}").change((e) => @on_click_display(e))
        return @

    cl_inputs: ['minhfsigma', 'maxhfsigma', 'minextension', 'maxextension']

    on_click_display: (evt) ->
        evt.preventDefault()
        evt.stopPropagation()

        tmp = evt.target.id.split('-')
        id  = Number(tmp[tmp.length-1])
        if id == @model.displaytype
            return

        $(@el).find("#dpx-rp-displaytype-#{@model.displaytype}").prop('checked', false)
        $(@el).find("#dpx-rp-displaytype-#{id}").prop('checked', true)
        @model.displaytype = Number(id)

    mk_inp: (name, maxv = 100, dv = 0.1) ->
        disabled = if @model.frozen then ' disabled=true' else ''
        return  "<input id='dpx-rp-#{name}'"+
                    " class='dpx-rp-freeze bk-widget-form-input'"+
                    " type='number' min=0 max=#{maxv} step=#{dv} "+
                    " value=#{@model[name]}#{disabled}>"

export class DpxRamp extends Widget
    default_view: DpxRampView
    type:         "DpxRamp"

    initialize: (attributes, options) ->
        super(attributes, options)
        @css_classes = ["dpx-ramp", "dpx-widget"]

    @define {
        frozen: [p.Bool, true],
        minhfsigma: [p.Number, 1e-4],
        maxhfsigma: [p.Number, 5e-3],
        minextension: [p.Number, .05],
        fixedextension: [p.Number, .4],
        maxextension: [p.Number, 1.5],
        displaytype: [p.Number, 0]
    }
