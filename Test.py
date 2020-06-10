#!/usr/bin/env python
# coding: utf-8

# In[1]:


#
# import the SiPM classes
#
from SiPM import *
# for plotting
import matplotlib
import matplotlib.pyplot as plt
get_ipython().run_line_magic('matplotlib', 'inline')


# In[2]:


# z position of the in-plane SiPMs
z_plane = 10
# radius of the cyinder for SiPMs at the side
r_cylinder = 22
# radius of a SiPM - I assume circular SiPMs with a radius to make the area correspond to a 3x3mm2 square.
r_sipm = 1.6925
# build geometry
geo = GeoParameters(z_plane=z_plane, r_cylinder=r_cylinder, r_sipm=r_sipm)


# In[3]:


# generate a XAMS geometry with SiPMs in plane above the LXe

# center SiPMs
sipm = SiPM(type="plane",position=[0,4,z_plane],qeff=0.25)
geo.add_sipm(sipm)
sipm = SiPM(type="plane",position=[0,-4,z_plane],qeff=0.25)
geo.add_sipm(sipm)

# ring SiPMs
n_circ = 6
r = 17.5
for phi in np.linspace(0,2*np.pi,n_circ,endpoint=False):
    sipm = SiPM(type="plane",position=[r*np.cos(phi),r*np.sin(phi),z_plane],qeff=0.25)
    geo.add_sipm(sipm)


# In[4]:


n_mc = 1000
sims = []
xbins = 2
ybins = 2
xmax = 20
ymax = 20

for x in np.linspace(0,xmax,xbins,endpoint=True):
    for y in np.linspace(0,ymax,ybins,endpoint=True):
        print("simulate @ x= ",x," mm", "simulate @ y= ",y, "mm")
        sim = Simulator(geo=geo,uv_position=[x,y,0],n_mc=n_mc)
        sim.generate_events()
        sims.append(sim)


# In[5]:


recs = []
for sim in sims:
    rec = Reconstruction(sim=sim)
    rec.emulate_events(n_uv=50000,n_event=10,method="CHI2",plot=False,nbins=1000,range=((-30,30),(-30,30)))
    recs.append(rec)


# In[6]:


ana = Analysis(recs=recs, xsize=xbins, ysize=ybins, xmax= xmax, ymax=ymax)

ana.merge()
ana.plot(type = "xdif")


# In[7]:


#import matplotlib.pyplot as plt
#import numpy as np
#from mpl_toolkits.axes_grid1.anchored_artists import AnchoredDirectionArrows
#import matplotlib.font_manager as fm

#fig, ax = plt.subplots()
#ax.imshow(np.random.random((10, 10)))

#simple_arrow = AnchoredDirectionArrows(ax.transAxes, 'X', 'Y')
#ax.add_artist(simple_arrow)

#high_contrast_part_1 = AnchoredDirectionArrows(
#                            ax.transAxes,
#                            '111', r'11$\overline{2}$',
#                            loc='upper right',
#                            arrow_props={'ec': 'w', 'fc': 'none', 'alpha': 1,
#                                         'lw': 2}
#                            )
#ax.add_artist(high_contrast_part_1)


# In[8]:


#import matplotlib.pyplot as plt
#from matplotlib.offsetbox import AnchoredText


#fig, ax = plt.subplots(figsize=(3, 3))

#at = AnchoredText("", prop=dict(size=15), frameon=True, loc='upper left')

#ax.add_artist(at)
#at.patch.set_boxstyle("round,pad=0.,rounding_size=0.2")


#sq = plt.Rectangle(xy=(xs[0] - dx / 2, xs[1] - dx / 2),
#                    height=dx,
#                    width=dx,
#                    fill=False, color='blue')
#            ax.add_artist(sq)

#plt.show()


# In[ ]:





# In[ ]:




