    on_change_bounds: (fig, src) ->
        yrng = fig.y_range
        if yrng._initial_start? && yrng.bounds != null
            yrng._initial_start = yrng.bounds[0]
            yrng._initial_end   = yrng.bounds[1]

        bases        = fig.extra_y_ranges['bases']
        bases.start  = (yrng.start - @bias)*@stretch
        bases.end    = (yrng.end   - @bias)*@stretch

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
            dur.end = Math.max.apply(Math, src.data["duration"][ix1..ix2])
            cnt.end = Math.max.apply(Math, src.data["count"][ix1..ix2])

    on_change_sequence: (src, peaks, stats, tick1, tick2, menu) ->
        if menu.value in src.column_names
            menu.label       = menu.value
            tick1.key        = menu.value
            tick2.key        = menu.value
            src.data['text'] = src.data[menu.value]
            src.change.emit()

            if stats.data[menu.value]?
                stats.text = stats.data[menu.value]

            if menu.value+'id' in peaks.source.column_names
                for key in ['id', 'bases', 'distance', 'orient', 'color']
                    peaks.source.data[key] = peaks.source.data[menu.value+key]
                peaks.source.change.emit()

            if menu.value in @stretches
                @updating = 'seq'
                @stretch  = @stretches[menu.value]
                @bias     = @biases   [menu.value]
                @updating = '*'
                @updating = ''