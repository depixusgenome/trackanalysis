import * as p         from "core/properties"
import {RowView, Row} from "models/layouts/row"
import {ToolbarBox}   from "models/tools/toolbar_box"

export class DpxDAQCameraView extends RowView
    className: "dpx-bk-grid-row"
    build_child_views: () ->
        super()
        cnt = document.createElement("div");   cnt.id  = 'dpxdaqcontainer'
        cam = document.createElement("div");   cam.id  = 'dpxdaqwrapper'
        emb = document.createElement("embed"); emb.id  = 'dpxdaqvlc'
        emb.setAttribute('type',        'application/x-vlc-plugin')
        emb.setAttribute('pluginspage', 'http://www.videolan.org')
        emb.setAttribute('controls',    'false')
        emb.setAttribute('branding',    'false')
        emb.setAttribute('autoplay',    'yes')
        emb.setAttribute('loop',        'no')
        emb.setAttribute('windowless',  'true')
        cam.appendChild(emb)
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
        figwidth:  [p.Number, 800],
        figheight: [p.Number, 400],
        start:     [p.Number, -1],
        stop:      [p.Number, -1],
    }
