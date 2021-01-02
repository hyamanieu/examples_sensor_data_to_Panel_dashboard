#!/usr/bin/env python
# coding: utf-8

# In[20]:


#imports for mqtt
import json
from paho.mqtt import subscribe, client
import os
import socket

#imports for visualization
import panel as pn

import holoviews as hv
from bokeh.transform import linear_cmap
from bokeh import palettes
from bokeh.themes.theme import Theme
import param

#imports for data proc
from numpy import nan
import datetime


# In[21]:



from bokeh.themes.theme import Theme

theme = Theme(
    json={
    'attrs' : {
        'Figure' : {
            'outline_line_width': 0,
        },
    }
})


# In[22]:


css = '''
.bk.panel-widget-box {
  background: #f0f0f0;
  border-radius: 5px;
  border: 1px black solid;
}
'''

pn.extension(raw_css=[css])
hv.extension('bokeh')


# In[23]:


MQTT_USER = os.getenv('MQTT_USER')
MQTT_PASSWORD= os.getenv('MQTT_PASSWORD')
MQTT_ADDRESS= os.getenv('MQTT_ADDRESS')


# In[24]:


hv.renderer('bokeh').theme = theme


# In[25]:


topics = {"zigbee2mqtt/TH_bureau":"bureau",
          "zigbee2mqtt/TH_Paul":"paul",
          "zigbee2mqtt/TH_Salon":"salon",
          "zigbee2mqtt/TH_SDB":"sdb",
          "zigbee2mqtt/TH_Cuisine":"cuisine",
          "zigbee2mqtt/TH_Entree":"entree",
          "zigbee2mqtt/TH_CageEscalier":"cage_desc",
          "zigbee2mqtt/TH_Chambre":"chambre",
}


# In[26]:


shiny_names = {
    "bureau":"Bureau",
    "paul":"Paul",
    "salon":"Salon",
    "sdb":"S. de bain",
    "cuisine": "Cuisine",
    "entree": "Entrée",
    "cage_desc": "Cage d'escalier",
    "chambre": "Chambre"
    }


# In[27]:


def fetch_first_message(topic):
    msg = subscribe.simple(topic,hostname=MQTT_ADDRESS,auth={'username':MQTT_USER,'password':MQTT_PASSWORD},
                     retained=True,
                     will={'topic':topic,'retain':True})
    payload = json.loads(msg.payload)
    payload.setdefault('linkquality',None)#in case it is missing from message
    for k, v in payload.items():
        #make all of them floats
        if k in ['pressure','temperature','humidity']:
            payload[k] = float(v)
    return payload


# In[28]:


sensor_streams = {room: hv.streams.Stream.define(room,
                                    **fetch_first_message(channel))() for channel, room in topics.items()}


# In[29]:


def room_plots(humidity,temperature,pressure,voltage,battery,linkquality=None,room_name='room'):
    
    
    def value_plot(value,unit='°C',palette=palettes.Plasma5,ylim=(-20,40),low=0,high=40,):
    
        scat = hv.Scatter({0:value})
        spik = hv.Spikes(scat)
        hv.Bars(scat)
        lab = hv.Text(x=0,y=value,text=f"{value}{unit}")

        mapper = linear_cmap(field_name='y',palette=palette,low=low,high=high)

        opts=dict(ylim=ylim,
                  color=mapper,responsive=True,
                  xaxis=None,yaxis=None,
                  toolbar='disable',
                  min_width=80,
                  height=150,
                  border=0)
        layout = (spik*scat*lab).opts(
                                        hv.opts.Scatter(size=80,**opts),
                                        hv.opts.Spikes(line_width=3,**opts),
                                        hv.opts.Text(color='black'),

        )
        
        return layout.opts(shared_axes=False)
    
    
    temp_layout = value_plot(temperature)
    
    hum_layout = value_plot(humidity,unit='%',palette=palettes.YlGnBu5[::-1],ylim=(0,100),low=20,high=100)
    
    
    press_layout = value_plot(pressure,unit='\nhPa',palette=palettes.Spectral5,ylim=(800,1200),low=900,high=1100)
   
    
    colors = "info" if battery > 20 else "danger"
    batt_pane = pn.indicators.Progress(name='battery',
                                       value=int(battery),
                                       max=100,width=50,height=20,
                                       bar_color=colors)
    
    
    colors = "warning" if (linkquality and linkquality > 20) else "danger"
    lqual_pane = pn.indicators.Progress(name='linkquality',
                                        width=50,height=20,
                                      bar_color=colors,
                                       align='end')
    lqual_pane.max=255#panel version 10.2, max must be changed after creating Progress instance.
    lqual_pane.value=int(linkquality) if linkquality else None
    
    
    layout = pn.Column(pn.Row(pn.layout.HSpacer(),pn.pane.Markdown(f'##{room_name}'),pn.layout.HSpacer()),
                        pn.Row(temp_layout,hum_layout,press_layout),
                        pn.Row(batt_pane, pn.layout.HSpacer(),lqual_pane),
                        css_classes=['panel-widget-box'])
    
    return layout


# In[30]:


#define functions, each of which depends on each stream. 
plot_funcs = {}
for k,room in sensor_streams.items():
    def rename_func(name):
        @param.depends(humidity = room.param.humidity,
                       temperature = room.param.temperature,
                       pressure = room.param.pressure,
                       voltage = room.param.voltage,
                       battery = room.param.battery,
                       linkquality = room.param.linkquality)
        def show_room(humidity,temperature,pressure,voltage,battery,linkquality):
            return room_plots(humidity,temperature,pressure,voltage,battery,linkquality,
                              room_name=shiny_names[name])        
        show_room.__name__ = f"show_{name}_room"
        return show_room
    plot_funcs[k]=rename_func(k)


# In[31]:


Info = pn.pane.Markdown('## Dernière info:')

gspec = pn.GridSpec(sizing_mode='stretch_both', max_height=1200)

#top floor
gspec[0,0]=plot_funcs['paul']
gspec[0,1]=plot_funcs['bureau']
gspec[0,2]=Info
#top_floor = pn.Row(plot_funcs['paul'],
#                   plot_funcs['bureau'],
#                   Info)
#bot_floor_east
gspec[1,0]=plot_funcs['chambre']
gspec[1,1]=plot_funcs['salon']
gspec[1,2]=plot_funcs['entree']
#bot_floor_east = pn.Row(plot_funcs['chambre'],
#                        plot_funcs['salon'],
#                        plot_funcs['entree'])
#bot_floor_west
gspec[2,0]=plot_funcs['cuisine']
gspec[2,1]=plot_funcs['sdb']
gspec[2,2]=plot_funcs['cage_desc']
#bot_floor_west = pn.Row(plot_funcs['cuisine'],
#                        plot_funcs['sdb'],
#                        plot_funcs['cage_desc'])

#flat = pn.Column(top_floor, bot_floor_east, bot_floor_west,height=800,width=1000)
flat = gspec


# In[32]:


myclient = client.Client(client_id=socket.gethostname(),)


# In[33]:


myclient.username_pw_set(MQTT_USER,password=MQTT_PASSWORD)


# In[34]:


myclient.connect(MQTT_ADDRESS)


# In[35]:


def on_message(client, userdata, message):
    room = topics[message.topic]
    payload = json.loads(message.payload)
    ts = datetime.datetime.fromtimestamp(message.timestamp).isoformat()
    Info.object=f'## Dernière info:\n- depuis: {message.topic}\n- date: {datetime.datetime.now().isoformat()}'
    sensor_streams[room].event(**payload)


# In[36]:


myclient.loop_start()
myclient.subscribe(list((chan,0) for chan in topics.keys()))
myclient.on_message = on_message


# In[37]:


flat.servable()

