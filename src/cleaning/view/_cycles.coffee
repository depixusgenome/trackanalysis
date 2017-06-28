import *        as $    from "jquery"
import *        as p    from "core/properties"
import {Model}          from "model"
import {BokehView} from "core/bokeh_view"

export class DpxCyclesPlotView extends BokehView

export class DpxCyclesPlot extends Model
    default_view: DpxCyclesPlotView
    type:         "DpxCyclesPlot"

    onchangebounds: () ->
        trng = @figure.extra_x_ranges['time']
        xrng = @figure.x_range
        if xrng.bounds is not None:
            xrng._initial_start = xrng.bounds[0]
            xrng._initial_end   = xrng.bounds[1]

        trng.start = xrng.start/@framerate
        trng.end   = xrng.end  /@framerate

    @define { framerate: [p.Number, 30.], figure: [p.Instance, {}]}
