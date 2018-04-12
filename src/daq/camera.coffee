import * as p         from "core/properties"
import {RowView, Row} from "models/layouts/row"
import {ToolbarBox}   from "models/tools/toolbar_box"

export class DpxDAQCameraView extends RowView
    className: "dpx-bk-grid-row"
    build_child_views: () ->
        super()
        w   = @model.figsizes[0]
        h   = @model.figsizes[1]
        l   = @model.figsizes[2]
        t   = @model.figsizes[3]

        cnt = document.createElement("div");   cnt.id  = 'dpxdaqcontainer'
        cnt.style = 'position: relative;'

        cam       = document.createElement("div");   cam.id  = 'dpxdaqwrapper'
        cam.style = "top: #{t}px; left: #{l}px; width: #{w}px;"+
                    " height: #{h}px; position: absolute; overflow: hidden"

        emb = document.createElement("embed"); emb.id  = 'dpxdaqvlc'
        emb.setAttribute('type',        'application/x-vlc-plugin')
        emb.setAttribute('pluginspage', 'http://www.videolan.org')
        emb.setAttribute('controls',    'no')
        emb.setAttribute('branding',    'false')
        emb.setAttribute('autoplay',    'yes')
        emb.setAttribute('loop',        'no')
        emb.setAttribute('windowless',  'true')
        emb.setAttribute('width',       "#{w}")
        emb.setAttribute('height',      "#{h}")
        cam.appendChild(emb)

        codeobj = document.createElement("object")
        codeobj.setAttribute("classid",  "clsid:9BE31822-FDAD-461B-AD51-BE1D1C159921")
        codeobj.setAttribute("codebase", "http://download.videolan.org/pub/videolan/vlc/last/win32/axvlc.cab")
        codeobj.setAttribute("style",    "display:none;")
        cam.appendChild(codeobj)

        @el.children[0].style = 'position: absolute;'
        @el.insertBefore(cam, @el.firstChild)

    connect_signals: () ->
        super()
        @connect(@model.properties.start.change, @on_start_cam)
        @connect(@model.properties.stop.change, @on_stop_cam)
        return

    on_start_cam: () ->
        emb = document.getElementById("dpxdaqvlc")
        if emb.playlist?
            emb.playlist.items.clear()
            arr = Array(":rtsp-caching=0", ":network-caching=200")
            emb.playlist.add(@model.address, "live", arr)
            emb.playlist.play()

            fig = @model.get_layoutable_children()[0].get_layoutable_children()[0]
            rng = [fig.extra_x_ranges['xpixel'], fig.extra_y_ranges['ypixel']]
            @model.on_zoom(rng[0], rng[1])
        return

    on_stop_cam: () ->
        emb = document.getElementById("dpxdaqvlc")
        emb.playlist.items.clear()

export class DpxDAQCamera extends Row
    default_view: DpxDAQCameraView
    type: "DpxDAQCamera"

    on_zoom: (xax, yax)->
        emb   = document.getElementById("dpxdaqvlc")
        if emb?
            xvals = [Math.round(xax.start), Math.round(xax.end)]
            yvals = [Math.round(yax.start), Math.round(yax.end)]
            txt   = "#{xvals[1]-xvals[0]}x#{yvals[1]-yvals[0]}+#{xvals[0]}+#{yvals[0]}"
            emb.video?.crop = txt
            return

    @define {
        address:   [p.String, "rtsp://192.168.1.56:8554/mystream"],
        figsizes:  [p.Array,  [800, 400, 28, 5]],
        start:     [p.Number, -1],
        stop:      [p.Number, -1],
    }
