#!/usr/bin/env python
# coding: utf-8

# In[1]:


#imports for MQTT
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

#imports for data processing
from numpy import nan
import datetime


# In[2]:


pn.extension()
hv.extension('bokeh')


# If you've set a password for your MQTT broker, you could write in the cell below or use environemental variables as I do:

# In[3]:


MQTT_USER = os.getenv('MQTT_USER')
MQTT_PASSWORD= os.getenv('MQTT_PASSWORD')
MQTT_ADDRESS= os.getenv('MQTT_ADDRESS')


# Then each MQTT canal in a dic key, and I set its nickname as value. As example, we'll be using the office's sensor

# In[22]:


topics = {
          "zigbee2mqtt/TH_bureau":"bureau",
}


# We can now fetch data from this canal using the paho-mqtt library:

# In[23]:


topic = "zigbee2mqtt/TH_bureau"
msg = subscribe.simple(topic,#MQTT canal
                       hostname=MQTT_ADDRESS,#Broker's IP Address, either localhost or the RPi's address.
                       auth={'username':MQTT_USER,'password':MQTT_PASSWORD},
                     retained=True,will={'topic':topic,'retain':True}#Yes, we do want to fetch the last sent data even before suscribing to the canal
                      )


# Note the `retained=True` option would have been without effect would you have not set it in the broker configuration file.
# 
# Sensor's data are in *payload*, in binary.

# In[6]:


print(msg.payload)


# In[7]:


type(msg.payload)


# We can now use the *stream* module from *holoviews* package. A stream is simply a named tuple within which we can update each element for each coming new message comes from the sensor.

# In[8]:


room = "bureau"
payload = json.loads(msg.payload)#the bytestring JSON is translated into a python dic
Bureau_Stream = hv.streams.Stream.define(room,**payload)#the stream is initialised with the first message, stored in payload


# In[9]:


type(Bureau_Stream)


# A metaclass was created. Several streams could indeed have the same paramters and init but with different sources. We need now to create the streaming object:

# In[10]:


bureau_stream = Bureau_Stream()


# In[11]:


type(bureau_stream)


# Let's now subscribe to the *TH_Chambre* channel to feed our *bureau_stream* object. Rather than using *subscribe* function, we will create a MQTT client.
# 
# I give it a name with `client_id`. We could also the library let it give it a random name. It could be more practical: the broker accepts only one client with a given id.

# In[12]:


myclient = client.Client(client_id="my_beautiful_client",)#instanciated
myclient.username_pw_set(MQTT_USER,password=MQTT_PASSWORD)#authentification
myclient.connect(MQTT_ADDRESS)# then we connect


# Zero indicates that connection was successfull. We now do two things:
# 1. we make a function that will feed our *holoviews* stream with new data
# 2. let our MQTT client sub to the *TH_bureau* channel.

# In[13]:


topics["zigbee2mqtt/TH_bureau"]


# In[14]:


def on_message(client, userdata, message):
    room = topics[message.topic]#The channel name is translated by a friendlier nickname.
    payload = json.loads(message.payload)#broker's bytestring into a python dictionnary
    bureau_stream.event(**payload)#We make an event. Each element is fed with fresh data


# In[15]:


myclient.loop_start()#this method is meant to listen for new message in a different thread so we don't lock this one.
res = myclient.subscribe(("zigbee2mqtt/TH_bureau",0) )#the MQTT client subs to the TH_Chambre channel.
print("Success if zero: {0}, mid: {1}".format(*res))
myclient.on_message = on_message# we set the callback


# In[16]:


bureau_stream


# Some time later...

# In[21]:


bureau_stream


# The *stream* can now be visualized. For this, we create a function that will return a *holoviews* object. Panel being what it is, it can accept this kind of function to create a dynamic *Pane*. Our dashboard will be dynamic!
# 
# Each time new data comes in, the plot must update. We use the *depends* decorator for this from *param*'s library. It is used by Holoviews and Panel. Notice how the decorator's paramters are named as the function parameters.

# In[18]:


COUNTER = 0
@param.depends(humidity = bureau_stream.param.humidity,
               temperature = bureau_stream.param.temperature,
               pressure = bureau_stream.param.pressure,
               voltage = bureau_stream.param.voltage,
               battery = bureau_stream.param.battery,
               linkquality = bureau_stream.param.linkquality)
def room_plots(humidity,temperature,pressure,voltage,battery,linkquality=None,room_name='room'):
    """
    On prend en entrée chaque valeur dans le JSON du canal MQTT. Linkquality peut être absent.
    Room_name est simplement le nom de la salle, ici le bureau.
    
    """
    global COUNTER
    COUNTER += 1
    
    def value_plot(value,unit='°C',palette=palettes.Plasma5,ylim=(-20,40),low=0,high=40,):
        """
        On représente les mesures environnementales (température, humidité, pression) avec un
        baton et un rond dans lequel sera inscrit la valeur numérique.
        """
    
        scat = hv.Scatter({0:value})#le rond en position 0
        spik = hv.Spikes(scat)#le baton au même endroit
        lab = hv.Text(x=0,y=value,text=f"{value}{unit}")#la valeur numérique et l'unité

        mapper = linear_cmap(field_name='y',palette=palette,low=low,high=high)#la couleur du rond dépend de la valeur

        opts=dict(ylim=ylim,#on donne la même limite à tous
                  color=mapper,responsive=True,#la dimension sera dynamique ou "responsive"
                  xaxis=None,yaxis=None,#pas d'axe pour aléger
                  toolbar='disable',#pas besoin de zoomer ou autre...
                  min_width=80,
                  height=150,
                  border=0)
        layout = (spik*scat*lab).opts(#on met le label tout au dessus, puis le rond, puis le baton caché derrière
                                        hv.opts.Scatter(size=80,**opts),
                                        hv.opts.Spikes(line_width=3,**opts),
                                        hv.opts.Text(color='black'),

        )
        
        return layout.opts(shared_axes=False)
    
    
    temp_layout = value_plot(temperature)
    
    hum_layout = value_plot(humidity,unit='%',palette=palettes.YlGnBu5[::-1],ylim=(0,100),low=20,high=100)
    
    
    press_layout = value_plot(pressure,unit='\nhPa',palette=palettes.Spectral5,ylim=(800,1200),low=900,high=1100)
   
    #la qualité de liaison et le niveau de batterie est montré par une barre de progression.
    #non seulement c'est esthétique, mais cela accepte None dans le cas où la qualité manque.
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
    lqual_pane.max=255#panel version 10.2, max must be changed after creating Progress instance. Fixed in next version.
    lqual_pane.value=int(linkquality) if linkquality else None
    
    #on met nos 5 représentations des 5 valeurs dans des colonnes et des lignes Panel.
    layout = pn.Column(pn.Row(pn.layout.HSpacer(),pn.pane.Markdown(f'##{room_name}'),pn.layout.HSpacer()),
                        pn.Row(temp_layout,hum_layout,press_layout),
                        pn.Row(batt_pane, pn.layout.HSpacer(),lqual_pane),
                        pn.pane.Markdown(f'Lu {COUNTER} fois'))
    
    return layout


# In[19]:


pn.panel(room_plots)


# And voilà! The same can be done for each MQTT channel, in other words for each sensor.
# There are certainly things to do better for each sensor.

# In[ ]:




