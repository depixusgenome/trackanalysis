    set_hover: (rawsrc, hvrsrc, glyph, inds, value) ->
        if @_hvr_cnt != value
            return

        inds.sort((a,b) => a - b)
        ind = inds[Math.floor(inds.length*0.5)]
        ind = Math.floor(ind/@shape[1]) * @shape[1]
        if ind == @cycle
            return

        @cycle           = ind
        hvrsrc.data['z'] = rawsrc.data['z'][ind...(ind+@shape[1])]
        glyph.visible    = true
        hvrsrc.change.emit()

    launch_hover: (rawsrc, hvrsrc, glyph) ->
        if @shape[1] == 2
            return
        if not rawsrc.selected?
            return

        @_hvr_cnt = if @_hvr_cnt? then @_hvr_cnt + 1 else 0
        inds      = rawsrc.selected.indices
        if (not inds?) || inds.length == 0
            if glyph.visible
                glyph.visible = false
                glyph.change.emit()
            return

        @set_hover(rawsrc, hvrsrc, glyph, inds, @_hvr_cnt)

    on_change_hist_bounds: (fig, src)->
        if not fig.y_range?
            return

        if not fig.extra_x_ranges?
            return

        cycles = fig.extra_x_ranges['cycles']
        frames = fig.x_range

        cycles.start = 0
        frames.start = 0

        yrng         = fig.y_range
        bases        = fig.extra_y_ranges['bases']
        bases.start  = (yrng.start - @bias)*@stretch
        bases.end    = (yrng.end   - @bias)*@stretch

        bottom       = src.data['bottom']
        if bottom.length < 2
            ind1 = 1
            ind2 = 0
        else
            delta = bottom[1]-bottom[0]
            ind1  = Math.min(bottom.length, Math.max(0, (yrng.start-bottom[0])/delta-1))
            ind2  = Math.min(bottom.length, Math.max(0, (yrng.end-bottom[0])/delta+1))

        if ind1 >= ind2
            cycles.end = 0
            frames.end = 0
        else
            frames.end = Math.max.apply(Math, src.data['frames'][ind1..ind2])+1
            cycles.end = Math.max.apply(Math, src.data['cycles'][ind1..ind2])+1

    on_change_raw_bounds: (frng, trng) ->
        if trng.reset_start? && trng.bounds != null
            trng.reset_start = trng.bounds[0]
            trng.reset_end   = trng.bounds[1]
        trng.start = frng.start/@framerate
        trng.end   = frng.end  /@framerate

    on_change_peaks_table: (peaks) ->
        if @updating != ''
            return

        zval  = peaks.data['z']
        bases = peaks.data['bases']
        if zval[0] == zval[1] || bases[0] == bases[1]
            return

        aval = (bases[1]-bases[0])/(zval[1]-zval[0])
        bval = zval[0] - bases[0]/aval

        if Math.abs(aval - @stretch) < 1e-2 and Math.abs(bval-@bias) < 1e-5
            return

        @stretch   = aval
        @bias      = bval
        @updating  = 'table'

    on_change_stretch: (stretch)->
        if @updating != ''
            return

        if Math.abs(stretch.value - @stretch) < 1e-2
            return

        @stretch  = stretch.value
        @updating = 'stretch'

    on_change_bias: (bias)->
        if @updating != ''
            return

        if Math.abs(bias.value - @bias) < 1e-5
            return

        @bias     = bias.value
        @updating = 'bias'

    on_change_hover: (table, stretch, bias, fig, ttip)->
        if @updating == ''
            return

        if @updating != 'table'
            bases = table.data["bases"]
            aval  = bases[0] / @stretch + @bias
            bval  = bases[1] / @stretch + @bias
            if Math.abs(aval-table.data['z']) < 1e-5 && Math.abs(bval-table.data['z']) < 1e-5
                return

            table.data["z"] = [aval, bval]
            table.properties.data.change.emit()

        if @updating != 'stretch'
            stretch.value = @stretch

        if @updating != 'bias'
            bias.value = @bias

        @apply_update(fig, ttip)
