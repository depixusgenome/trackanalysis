p         = require "core/properties"
BokehView = require "core/bokeh_view"
Model     = require "model"
$         = require "jquery"

class DpxKeyEventView extends BokehView
    initialize: (options) ->
        super(options)
        $(document).keydown((e) => @_key_down(e))

    _key_down: (evt) ->
        val = ""
        for name, kw of {alt: 'Alt'; shift: 'Shift'; ctrl: 'Control'; meta: 'Meta'}
            if evt[name+'Key']
                 val += "#{kw}-"
        val = if val == (evt.key+'-') then evt.key else val + evt.key
        if val in @model.keys
            evt.preventDefault()
            evt.stopPropagation()
            @model.value = val
            @model.count = @model.count+1

class DpxKeyEvent extends Model
    default_view: DpxKeyEventView
    type:"DpxKeyEvent"

    @define {
        keys:  [p.Array, []]
        value: [p.String, ""]
        count: [p.Int, 0]
    }

module.exports =
  Model: DpxKeyEvent
  View:  DpxKeyEventView
