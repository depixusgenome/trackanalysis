import {build_views}    from "core/build_views"
import {logger}         from "core/logging"
import *        as $    from "jquery"
import *        as p    from "core/properties"
import {LayoutDOMView, LayoutDOM} from "models/layouts/layout_dom"

export class DpxCleaningView extends LayoutDOMView
    tagName: "div"

    initialize: (options) ->
        super(options)
        @render()
        for evt in @cl_inputs
            @listenTo(@model, 'change:#{name}', do (evt, me = @) ->
                      () -> $(me.el).find("#dpx-cl-#{evt}").val("#{me.model[evt]}"))
        @listenTo(@model, 'change:frozen',
                  () => $(@el).find('.dpx-cl-freeze').prop('disabled', @model.frozen))

    render: () ->
        super()
        html = "<div class='dpx-cleaning'><span class='dpx-row'>"+
                   "<label>|z|     ≤</label>#{@mk_inp("maxabsvalue")}"+
                   "<label>|dz/dt| ≤</label>#{@mk_inp("maxderivate")}"+
               "</span><span class='dpx-row'>"+
                   "<label>Δz      ≥</label>#{@mk_inp("minextent")}"+
                   "<label>% good  ≥</label>#{@mk_inp("minpopulation", step = 0.1)}"+
               "</span><span class='dpx-row'>"+
                   "#{@mk_inp("minhfsigma", step = 0.0001, maxv = 0.01)}"+
                   "<label>≤ σ[HF] ≤</label>"+
                   "#{@mk_inp("maxhfsigma", step = 0.0001, maxv = 0.01)}"+
               "</span></div>"

        elem = $(@el)
        elem.html(html)
        for evt in @cl_inputs
            el = elem.find("#dp-cl-#{evt}")
            el.change(do (mdl = @model, el, evt) -> () -> mdl[evt] = Number(el.val()))
        return @

    cl_inputs: ['maxabsvalue', 'maxderivate', 'minpopulation', 'minhfsigma',
                'maxhfsigma', 'minextent']

    mk_inp: (name, maxv = 100, dv = 0.1) ->
        return  "<input id='dpx-cl-#{name}'"+
                    " class='dpx-cl-freeze bk-widget-form-input'"+
                    " type='number' min=0 max=#{maxv} step=#{dv} "+
                    " value=#{@model[name]} disabled=true>"

    set_pyevent: (name) ->


export class DpxCleaning extends LayoutDOM
    default_view: DpxCleaningView
    type:         "DpxCleaning"

    onchangebounds: () ->
        trng = @figure.extra_x_ranges['time']
        xrng = @figure.x_range
        if xrng.bounds is not None
            xrng._initial_start = xrng.bounds[0]
            xrng._initial_end   = xrng.bounds[1]

        trng.start = xrng.start/@framerate
        trng.end   = xrng.end  /@framerate

    @define {
        frozen: [p.Bool, true],
        framerate: [p.Number, 30],
        figure: [p.Instance, {}],
        maxabsvalue: [p.Number, 5],
        maxderivate: [p.Number, 2],
        minpopulation: [p.Number, 80],
        minhfsigma: [p.Number, 1e-4],
        maxhfsigma: [p.Number, 1e-2],
        minextent: [p.Number, .5]
    }
