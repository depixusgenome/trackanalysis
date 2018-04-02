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
        cam.style = "top: #{t}px; left: #{l}px; width: #{w}px; height: #{h}px; position: absolute;"

        emb = document.createElement("embed"); emb.id  = 'dpxdaqvlc'
        emb.setAttribute('type',        'application/x-vlc-plugin')
        emb.setAttribute('pluginspage', 'http://www.videolan.org')
        emb.setAttribute('controls',    'false')
        emb.setAttribute('branding',    'false')
        emb.setAttribute('autoplay',    'yes')
        emb.setAttribute('loop',        'no')
        emb.setAttribute('windowless',  'true')
        emb.setAttribute('width',       "#{w}")
        emb.setAttribute('height',      "#{h}")
        cam.appendChild(emb)

        @el.children[0].style = 'position: absolute;'
        @el.appendChild(cam)

    connect_signals: () ->
        super()
        @connect(@model.properties.start.change, @on_start_cam)
        @connect(@model.properties.stop.change, @on_stop_cam)

    @on_start_cam: () ->
        emb = document.getElementById("dpxdaqvlc")
        emb.playlist.items.clear()
        arr = Array(":rtsp-caching=0", ":network-caching=200")
        emb.playlist.add(@model.addresss, "livedaqcamera", arr)
        emb.playlist.play()

    @on_stop_cam: () ->
        emb = document.getElementById("dpxdaqvlc")
        emb.playlist.items.clear()

export class DpxDAQCamera extends Row
    default_view: DpxDAQCameraView
    type: "DpxDAQCamera"
    @define {
        address:   [p.String, "rtsp://192.168.1.56:8554/mystream"],
        figsizes:  [p.Array,  [800, 400, 28, 5]],
        start:     [p.Number, -1],
        stop:      [p.Number, -1],
    }
