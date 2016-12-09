#!/usr/bin/env python3
# -*- coding: utf-8 -*-
u"Runs an app"
import click

@click.command()
@click.argument('view')
@click.option("--app", default = 'withtoolbar',
              help = u'Which app mixin to use')
@click.option("--web", 'desktop', flag_value = False,
              help = u'Serve to webbrowser rather than desktop app')
@click.option("--desk", 'desktop', flag_value = True, default = True,
              help = u'Launch as desktop app')
@click.option("--show", flag_value = True, default = False,
              help = u'If using webbrowser, launch it automatically')
def run(view, app, desktop, show):
    u"Launches an view"
    if view.startswith('view.'):
        view = view[5:]

    if '.' not in view:
        view = view.lower()+'.'+view

    if view == 'toolbar.ToolBar':
        app = 'default'

    viewmod  = __import__('view.'+view[:view.rfind('.')],
                          fromlist = view[view.rfind('.')+1:])
    viewcls  = getattr(viewmod, view[view.rfind('.')+1:])

    if app.startswith('app.'):
        app = app[5:]

    launchmod = __import__('app.'+app, fromlist = (('serve', 'launch')[desktop],))
    launch    = getattr(launchmod, ('serve', 'launch')[desktop])

    server    = launch(viewcls)
    if (not desktop) and show:
        server.io_loop.add_callback(lambda: server.show('/'))
    server.start()

if __name__ == '__main__':
    run()   # pylint: disable=no-value-for-parameter
