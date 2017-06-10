import * as p  from "core/properties"
import {Model} from "model"
import {BokehView} from "core/bokeh_view"

export class NAMEView extends BokehView
export class NAME     extends Model
    default_view: NAMEView
    type: "NAME"

    setsource: (source, value) ->
        if @_callcount != value
            return
        if @updating   != ''
            return

        @_callcount = value
        tmp = source.data["values"]
        source.data["z"] = tmp.map(((x)-> x/@stretch+@bias), @)
        source.trigger('change:data')

    apply_update: (fig, ttip) ->
        if @updating == ''
            return

        @_callcount = @_callcount + 1

        bases       = fig.extra_y_ranges['bases']
        yrng        = fig.y_range
        bases.start = (yrng.start - @bias) * @stretch
        bases.end   = (yrng.end   - @bias) * @stretch

        window.setTimeout(((b, c) => @setsource(b, c)),
                          800, ttip, @_callcount)
        @updating   = ''

    @define {
        framerate : [p.Number, 1],
        stretch   : [p.Number, 0],
        bias      : [p.Number, 0],
        updating  : [p.String, '']
    }

    @internal { _callcount: [p.Number, 0] }
