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

    launch_hover: (rawsrc, hvrsrc, glyph, selected) ->
        console.log("*", selected['1d'])
        if @shape[1] == 2
            return

        @_hvr_cnt = if @_hvr_cnt? then @_hvr_cnt + 1 else 0
        inds      = selected['1d'].indices
        if (not inds?) || inds.length == 0
            if glyph.visible
                glyph.visible = false
                glyph.change.emit()
            return

        window.setTimeout(((a,b,c,d,e) => @set_hover(a,b,c,d,e)),
                          100, rawsrc, hvrsrc, glyph,
                          inds, @_hvr_cnt)
