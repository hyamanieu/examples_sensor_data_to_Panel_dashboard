#!/usr/bin/env python
# coding: utf-8

# In[1]:


#imports pour le MQTT
import json
from paho.mqtt import subscribe, client
import os
import socket

#imports pour la visualisation
import panel as pn

import holoviews as hv
from bokeh.transform import linear_cmap
from bokeh import palettes
from bokeh.themes.theme import Theme
import param

#imports pour le traitement de données
from numpy import nan
import datetime


# In[2]:


pn.extension()
hv.extension('bokeh')


# Si vous avez mis un mot de passe à votre *broker* MQTT, vous pouvez le changer ci-dessous ou utiliser des variables d'environnement comme moi:

# In[3]:


MQTT_USER = os.getenv('MQTT_USER')
MQTT_PASSWORD= os.getenv('MQTT_PASSWORD')
MQTT_ADDRESS= os.getenv('MQTT_ADDRESS')


# Ensuite chaque canal MQTT est listé dans les clés d'un dictionnaire, et son petit nom comme valeur. On va prendre pour exemple celui dans le bureau:

# In[4]:


topics = {
          "zigbee2mqtt/TH_bureau":"bureau",
}


# On va maintenant récupérer les dernières valeurs du capteur dans le bureau avec la bibliothèque paho-mqtt:

# In[5]:


topic = "zigbee2mqtt/TH_bureau"
msg = subscribe.simple(topic,#le canal MQTT
                       hostname=MQTT_ADDRESS,#l'adresse du broker, soit localhost soit l'adresse IP du RPi.
                       auth={'username':MQTT_USER,'password':MQTT_PASSWORD},
                     retained=True,will={'topic':topic,'retain':True}#oui, on veut récupérer la dernière donnée déjà envoyé
                      )


# A noter que l'option `retained=True` aurait été sans effet si vous ne l'aviez pas activée dans la configuration du *broker*.
# 
# Les données du capteur se trouve dans *payload*.

# In[6]:


print(msg.payload)


# In[7]:


type(msg.payload)


# On va maintenant utiliser le module *stream* du package *holoviews*. Un stream est tout simplement une table dans laquelle on va pouvoir rajouter un élément à chaque fois qu'un nouveau message provient du capteur.

# In[8]:


room = "bureau"
payload = json.loads(msg.payload)#on traduit le bytestring JSON du broker en un dictionnaire
Bureau_Stream = hv.streams.Stream.define(room,**payload)#on initialise le stream avec ce premier message


# In[9]:


type(Bureau_Stream)


# Nous n'avons créé qu'une metaclasse. En effet plusieurs streams avec les mêmes paramètres mais différentes sources peut avoir être créé. Il faut créé notre nouvel objet ainsi:

# In[10]:


bureau_stream = Bureau_Stream()


# In[11]:


type(bureau_stream)


# On va maintenant s'abonner au canal *TH_Chambre* afin d'alimenter notre objet *bureau_stream*. Plutôt qu'utiliser la fonction *suscribe* de *paho-mqtt*, on va créer un client. 
# 
# Je lui donne un nom avec `client_id`. On pourrait aussi laisser à la bibliothèque le soin de donner un nom aléatoire, ce qui sera plus judicieux: en effet le broker n'accepte qu'un seul client, ou listener, par id.

# In[12]:


myclient = client.Client(client_id="my_beautiful_client",)#on donne le nom de la machine
myclient.username_pw_set(MQTT_USER,password=MQTT_PASSWORD)#authentification
myclient.connect(MQTT_ADDRESS)# et on se connecte


# Le zéro indique que le client a pu se connecter. On va maintenant faire deux choses:
# 1. créer une fonction qui va venir alimenter notre stream holoviews avec de nouvelles données
# 2. puis inscrire le client mqtt au canal TH_bureau

# In[13]:


topics["zigbee2mqtt/TH_bureau"]


# In[14]:


def on_message(client, userdata, message):
    room = topics[message.topic]#on traduit le nom du canal avec le dictionnaire par le nom plus court du stream
    payload = json.loads(message.payload)#on traduit le bytestring du broker en un dictionnaire python
    bureau_stream.event(**payload)#on crée l'événement. Chaque colonne est alimenté avec une nouvelle données


# In[15]:


myclient.loop_start()#mettre dans un autre thread le fait d'attendre puis récupérer un nouveau message
res = myclient.subscribe(("zigbee2mqtt/TH_bureau",0) )#on inscrit notre client MQTT au canal TH_Chambre
print("Réussi si zero: {0}, mid: {1}".format(*res))
myclient.on_message = on_message# on associe le callback.


# In[16]:


bureau_stream


# quelque temps plus tard...

# In[21]:


bureau_stream


# On peut maintenant visualiser ce *stream*, on va donc créer une fonction qui retournera un objet *holoviews*. Panel étant ce qu'il est, il pourra accepter cette fonction en entrée dans un *Pane* et nous aurons notre dashboard dynamique.
# 
# Pour que le graph se mette à jour, il faut lui indiquer de se mettre à jour à chaque fois que la valeur change. On va utiliser le décorateur *depends* de la bibliothèque *param*, utilisé par *Holoviews* comme *Panel*.
# Vous noterez que les paramètres du décorateur sont exactement les mêmes que les paramètres en entrée de la fonction qui retourne le graph.

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


# Et voilà, on peut faire la même chose pour chaque canal du *broker*, donc pour chaque capteur.
# Il y a certainement des points à améliorer quant à la présentation graphique...

# In[ ]:




