    on_change_bounds: (fig, src) ->
        @on_change_bases(fig)
        yrng = fig.y_range
        zval = src.data["z"]
        ix1  = 0
        ix2  = zval.length
        for i in [0..zval.length]
            if zval[i] < yrng.start
                ix1 = i+1
                continue
            if zval[i] > yrng.end
                ix2 = i
                break

        dur = fig.extra_x_ranges['duration']
        cnt = fig.x_range

        dur.start = 0
        cnt.start = 0
        if(zval.length < 2 || ix1 == ix2)
            dur.end = 0
            cnt.end = 0
        else
            dur.end = Math.max.apply(Math, src.data["duration"][ix1..ix2])*1.05
            cnt.end = Math.max.apply(Math, src.data["count"][ix1..ix2])*1.05

    on_change_bases: (fig) ->
        yrng               = fig.y_range
        bases              = fig.extra_y_ranges['bases']
        bases.start        = (yrng.start - @bias)*@stretch
        bases.end          = (yrng.end   - @bias)*@stretch
        bases.reset_start  = (yrng.reset_start - @bias)*@stretch
        bases.reset_end    = (yrng.reset_end   - @bias)*@stretch

    on_change_sequence: (src, peaks, stats, tick1, tick2, menu) ->
        if menu.value in Object.keys(src.data)
            good = false
            for i in menu.menu
                if (i?) && (i[1] == menu.value)
                    menu.label = i[0]
                    good       = true
                    break
            if !good
                menu.label = menu.value

            tick1.key        = menu.value
            tick2.key        = menu.value
            src.data['text'] = src.data[menu.value]
            src.change.emit()

            if stats.data[menu.value]?
                stats.text = stats.data[menu.value]

            emit = false
            for key in ['id', 'bases', 'distance', 'orient', 'color']
                col = peaks.source.data[menu.value+key]
                if col?
                    peaks.source.data[key] = col
                    emit                   = true
            if emit
                peaks.source.change.emit()

            if menu.value in @stretches
                @updating = 'seq'
                @stretch  = @stretches[menu.value]
                @bias     = @biases   [menu.value]
                @updating = '*'
                @updating = ''
