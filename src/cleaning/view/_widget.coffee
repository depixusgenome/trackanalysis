import {build_views}    from "core/build_views"
import *        as $    from "jquery"
import *        as p    from "core/properties"
import {WidgetView, Widget} from "models/widgets/widget"

export class DpxCleaningView extends WidgetView
    tagName: "div"

    on_change_frozen: () ->
        $(@el).find('.dpx-cl-freeze').prop('disabled', @model.frozen)

    on_input: (evt) ->
        @model[evt] = Number($(@el).find("#dpx-cl-#{evt}").val())

    on_change_input: (evt) ->
        $(@el).find("#dpx-cl-#{evt}").val("#{@model[evt]}")

    connect_signals: () ->
        super()
        for evt in @cl_inputs
            @connect(@model.properties[evt].change, do (event = evt, me = @) ->
                      () -> me.on_change_input(event))
        @connect(@model.properties.frozen.change,    () => @on_change_frozen())

    render: () ->
        super()
        html = "<div class='dpx-span'>"+
                   "<div><p>|z| ≤</p><p>Δz  ≥</p><p/></div>"+
                   "<div>#{@mk_inp("maxabsvalue")}"+
                        "#{@mk_inp("minextent")}"+
                        "#{@mk_inp("minhfsigma", 0.05, 0.0001)}</div>"+
                   "<div><p>|dz/dt| ≤</p><p>% good  ≥</p><p>≤ σ[HF] ≤</p></div>"+
                   "<div>#{@mk_inp("maxderivate")}"+
                        "#{@mk_inp("minpopulation", 100, 0.1)}"+
                        "#{@mk_inp("maxhfsigma", 0.05,  0.001)}</diV>"+
               "</div>"

        elem = $(@el)
        elem.html(html)
        for evt in @cl_inputs
            el = elem.find("#dpx-cl-#{evt}")
            el.change(do (mdl = @model, inp = el, event = evt) ->
                        () -> mdl[event] = Number(inp.val()))
        return @

    cl_inputs: ['maxabsvalue', 'maxderivate', 'minpopulation', 'minhfsigma',
                'maxhfsigma', 'minextent']

    mk_inp: (name, maxv = 100, dv = 0.1) ->
        disabled = if @model.frozen then ' disabled=true' else ''
        return  "<input id='dpx-cl-#{name}'"+
                    " class='dpx-cl-freeze bk-widget-form-input'"+
                    " type='number' min=0 max=#{maxv} step=#{dv} "+
                    " value=#{@model[name]}#{disabled}>"

export class DpxCleaning extends Widget
    default_view: DpxCleaningView
    type:         "DpxCleaning"

    initialize: (attributes, options) ->
        super(attributes, options)
        @css_classes = ["dpx-cleaning", "dpx-widget"]

    onchangebounds: () ->
        trng = @figure.extra_x_ranges['time']
        xrng = @figure.x_range
        if xrng.bounds?
            xrng._initial_start = xrng.bounds[0]
            xrng._initial_end   = xrng.bounds[1]

        trng.start = xrng.start/@framerate
        trng.end   = xrng.end  /@framerate

    @define {
        frozen: [p.Bool, true],
        framerate: [p.Number, 30],
        figure: [p.Instance],
        maxabsvalue: [p.Number, 5],
        maxderivate: [p.Number, 2],
        minpopulation: [p.Number, 80],
        minhfsigma: [p.Number, 1e-4],
        maxhfsigma: [p.Number, 1e-2],
        minextent: [p.Number, .5]
    }
