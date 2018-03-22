import * as p  from "core/properties"
import {Model} from "model"
import {DOMView} from "core/dom_view"

export class DpxDAQCameraView extends DOMView
    render: (options) ->
        super(options)
        fig = document.getElementByClassName(@model.figclass)[0]
        emb = document.getElementById("dpxdaqvlc")
        if(emb == null)
            cnt     = document.createElement("div");   cnt.id  = 'dpxdaqcontainer'
            play    = document.createElement('div');   play.id = 'dxpdaqplayer'
            cam     = document.createElement("div");   cam.id  = 'dpxdaqwrapper'
            emb     = document.createElement("embed"); emb.id  = 'dpxdaqvlc'
            emb.setAttribute('type',        'application/x-vlc-plugin')
            emb.setAttribute('pluginspage', 'http://www.videolan.org')
            emb.setAttribute('controls',    'false')
            emb.setAttribute('branding',    'false')
            emb.setAttribute('autoplay',    'yes')
            emb.setAttribute('loop',        'no')
            emb.setAttribute('windowless',  'true')

            play.appendChild(fig)
            cam.appendChild(emb)
            cnt.appendChild(cam)
            cnt.appendChild(play)

            fig.parentNode.replaceChild(cnt, fig)

        emb.setAttribute('width',  fig.style.width.replace('px', ''))
        emb.setAttribute('height', fig.style.height.replace('px', ''))
        emb.playlist.items.clear()
        arr = Array(":rtsp-caching=0", ":network-caching=200")
        emb.playlist.add(@model.addresss, "livedaqcamera", arr)
        emb.playlist.play()

export class DpxDAQCamera extends Model
    default_view: DpxDAQCameraView
    type:"DpxDAQCamera"
    @define {
        address:  [p.String, "rtsp://192.168.1.56:8554/mystream"],
        figclass: [p.String, "dpxdaqcamera"]
        #codebase: [p.String, "http://download.videolan.org/pub/videolan/"+
        #                     "vlc/last/win32/axvlc.cab"]
    }
