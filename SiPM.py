from iminuit import Minuit
import numpy as np
import pandas as pd

from copy import deepcopy

import matplotlib
import matplotlib.pyplot as plt
from matplotlib.colors import BoundaryNorm
from matplotlib.ticker import MaxNLocator

from IPython.display import clear_output

np.random.seed(12345)
inch = 25.4  # mm


# -----------------------------------------------------------------------------------#
class GeoParameters:
    """Definition of the key parameters needed for the simulations"""

    def __init__(self, z_plane, r_cylinder, r_sipm, wire_thickness, wire_spacing):
        # z of plane to intersect UV photons
        self.z_plane = z_plane  # mm
        # radius of cylinder to intersect UV photons
        self.r_cylinder = r_cylinder  # mm
        #  SiPM effective radius corresponding to 3x3mm2 sensor
        self.r_sipm = r_sipm  # mm
        self.a_sipm = np.pi * r_sipm ** 2
        self.sipms = []
        self.wirethicc = wire_thickness
        self.wirespacing = wire_spacing

    def add_sipm(self, sipm):
        self.sipms.append(sipm)

    def get_sipms(self):
        return self.sipms
    
    def get_wire_x(self):
        wire_x = []
        diameter_TPC = 45
        for i in range(int(diameter_TPC/self.wirespacing)):
            wire_x.append(-0.5*diameter_TPC+self.wirespacing*i)
        return wire_x

    def __copy__(self):
        G = GeoParameters(self.z_plane, self.r_cylinder, self.r_sipm)
        for sipm in self.sipms:
            G.add_sipm(sipm)
        return G

# -----------------------------------------------------------------------------------#
class SiPM:
    """ Class for a single silicon PM """

    def __init__(self, type, position, qeff):
        """__init__ Constructor """
        if type not in ("plane", "cylinder"):
            print("SiPM::__init__ ERROR wrong SiPM type selected")
        self.type = type  # type=plane or type=cylinder
        # SiPM position
        self.x = position
        # normal vector to the SiPM
        if type == "plane":
            # pointing down
            self.rhat = [0,0,-1]
        elif type == "cylinder":
            # pointing inward
            self.rhat = [-position[0],-position[1],0]
            self.rhat = self.rhat / np.linalg.norm(self.rhat)
        self.nhit = 0
        self.hit_probability = 0
        self.qe = qeff

    def get_qe(self):
        return self.qe

    def get_normal_vector(self):
        return self.rhat

    def set_hit_probability(self, p):
        """Set probability for a SiPM to detect a UV photon

        p: probability"""

        self.hit_probability = p

    def get_hit_probability(self):
        return self.hit_probability

    def set_phi_z(self, r, phi, z):
        # for the SiPMs on a cylinder
        self.type = "cylinder"
        self.x[0] = r * np.cos(phi)
        self.x[1] = r * np.sin(phi)
        self.x[2] = z

        # pointing inward
        self.rhat = [-self.x[0], -self.x[1], 0]
        self.rhat = self.rhat / np.linalg.norm(self.rhat)

    def set_xyz(self, x):
        self.type = "plane"
        # for the SiPMs on a cylinder
        self.x = x
        self.rhat = [0, 0, -1]


    def get_location(self):
        return self.x

    def get_type(self):
        return self.type

    def get_number_of_hits(self):
        return self.nhit

    def set_number_of_hits(self, n):
        self.nhit = n

# -----------------------------------------------------------------------------------#
class Simulator:
    """Simulation of SiPM acceptance"""

    def __init__(self, geo, uv_position, n_mc):
        self.n_mc = n_mc

        self.cost_range = [np.cos(0), np.cos(np.pi)]
        self.phi_range = [0, 2 * np.pi]
        # x0 of the UV photons
        self.x0 = np.array(uv_position)
        self.tdir = np.zeros(3)

        self.h_cost, self.h_cost_bins = np.histogram([], bins=1000, range=[-1.1, 1.1])
        self.h_cost_tmp = []
        # in order to alllocate new memory locations for lists inside geometry
        self.geo = deepcopy(geo)

    def get_x0(self):
        return self.x0

    def set_nmc(self, n_mc):
        self.n_mc = n_mc

    def Print(self):
        print("Number of SiPMs = ", len(self.geo.get_sipms()), " Generated hits from x=", self.get_x0())
        n = 0
        for pm in self.geo.get_sipms():
            print("%2d  (x,y,z) = (%4.1f, %4.1f, %4.1f) p(hit) = %7.5f  qe = %5.3f" %
                  (n, pm.get_location()[0], pm.get_location()[1], pm.get_location()[2], pm.get_hit_probability(),
                   pm.get_qe()))
            n = n + 1

    def generate_events(self):
        """ Generate events

            Photon trajectories are intersected with:
                1. a cylinder centered around (x,y) = (0,0) with radius r_cylinder. Currently only one
                cylinder is alllowed
                2. a plane a fixed height z=z_plane. Only one plane is alllowed.

            NOTE: It is assumed that all SiPMs are either located on the surface of the cylinder or in the plane
        """
        for sipm in self.geo.get_sipms():
            sipm.nhit = 0
        # n_mc events are generated
        for i in range(self.n_mc):
            if i % 100000 == 0:
                print("generated ", i, " events")
                self.fill_hist()

            # generate a single UV photon
            self.generate_uv()

            # intersect with plane
            s_plane = self.intersect_with_plane()
            # intersect with cylinder
            s_cylinder = self.intersect_with_cylinder()

            # coordinates of intersection with plane
            self.xint_plane = self.x0 + np.multiply(s_plane, self.tdir)
            # coordinates of intersection with cylinder
            self.xint_cylinder = self.x0 + np.multiply(s_cylinder, self.tdir)

            # check if the UV photon hits a SiPM
            for sipm in self.geo.get_sipms():
                self.hit_sipm(sipm)

        # calculate the hit probabilities
        for sipm in self.geo.get_sipms():
            p = sipm.get_number_of_hits() / self.n_mc
            # correct for the quantum efficiency
            p = p * sipm.qe
            sipm.set_hit_probability(p)

        self.Print()
        self.fill_hist()
        print("event generation done")

    def fill_hist(self):
        # cos theta distribution
        htemp, dummy = np.histogram(self.h_cost_tmp, bins=1000, range=[-1.1, 1.1])
        self.h_cost = self.h_cost + htemp
        self.h_cost_tmp = []

    def generate_uv(self):
        """ Generate a UV photon with random direction. The starting position
            of the photon is always the same (within this class)
        """
        cost = np.random.uniform(self.cost_range[0], self.cost_range[1])
        sint = np.sqrt(1 - cost ** 2)
        phi = np.random.uniform(self.phi_range[0], self.phi_range[1])
        self.tdir = [np.cos(phi) * sint, np.sin(phi) * sint, cost]
        # histogramming
        self.h_cost_tmp.append(self.tdir[2])

    def hit_sipm(self, sipm):
        """ Calculate whether a track hits a SiPM.
            If the SiPM is hit the number of hits is incremented.
        """
        x = [0, 0, 0]
        if sipm.get_type() == "plane":
            x = self.xint_plane
        elif sipm.get_type() == "cylinder":
            x = self.xint_cylinder
        else:
            print("Simulator::hit_sipm ERROR wrong sipm type found. sipm.get_type() =", sipm.get_type())

        dx = np.linalg.norm(x - sipm.get_location())
        if dx < self.geo.r_sipm:
            sipm.nhit = sipm.nhit + 1

    def intersect_with_cylinder(self):
        """ calculate intersect of UV photon with cylinder -
            Return the positive path length s+ """
        s = 0

        A = self.tdir[0] ** 2 + self.tdir[1] ** 2
        B = 2 * (self.x0[0] * self.tdir[0] + self.x0[1] * self.tdir[1])
        C = self.x0[0] ** 2 + self.x0[1] ** 2 - self.geo.r_cylinder ** 2

        # print("tdir = ",self.tdir, " |tdir|=",np.linalg.norm(self.tdir))
        # print("x0   = ",self.x0, " |x0|=",np.linalg.norm(self.x0))
        # print("Rcyl = ",self.geo.r_cylinder," A =",A," B=",B," C=",C," B2-4AC =",B**2-4*A*C)

        discriminant = B ** 2 - 4 * A * C;

        if discriminant >= 0:
            s0 = (-B + np.sqrt(discriminant)) / (2 * A)
            s1 = (-B - np.sqrt(discriminant)) / (2 * A)

            if s0 > s1:
                s = s0
            else:
                s = s1

        return s

    def intersect_with_plane(self):
        """ calculate intersect of UV photon with pllane -
            Return the positive path length s+ """
        if np.linalg.norm(self.tdir) > 1e-10:
            s = (self.geo.z_plane - self.x0[2]) / self.tdir[2]
        else:
            s = 0
        # only positive directions
        if s < 0:
            s = 0
        return s

#-------------------------------------------------------------------------------------------------#

class Reconstruction:
    def __init__(self, sim):
        self.sim = sim
        self.geo = sim.geo
        self.fix_rate0 = False
        
    def fix_parameter_CHI2(self, parameter, fix_value):
        if parameter == "rate0":
            self.fix_rate0 = True
            self.n0 = fix_value
        else:
            print("Reconstruction::fix_parameter_CHI2 BAD parameter type selected. parameter=", parameter)

    def generate_hit(self, nuv):
        # generate a hit based on the simulated response for a give position
        # assume a certain number of uv photons generated and account for the
        # appropriate statistical fluctuations

        self.nmeasured = []
        for sipm in self.geo.get_sipms():
            nexp = nuv * sipm.get_hit_probability()
            sipm.set_number_of_hits(np.random.poisson(nexp))

        return 0

    def reconstruct_position(self, method, **kwargs):
        self.rate0 = 0
        self.xrec = [0, 0, 0]
        self.status = 0

        fval = -1
        chi2 = -1

        self.method = method
        if method == "COG":
            n = 0
            xs = [0, 0, 0]
            for sipm in self.geo.get_sipms():
                xs = xs + np.multiply(sipm.get_location(), sipm.get_number_of_hits())
                n = n + sipm.get_number_of_hits()
            self.xrec = xs / n
            self.rate0 = -1
            self.status = 1

        else:  # model fit
            errordef = 0.0
            if method == "CHI2":
                errordef = 1.0
            elif method == "LNLIKE":
                errordef = 0.5
            else:
                print("Reconstruction::reconstruct_position() ERROR bad value of errordef:", errordef)

            self.lnlike = PosFit(self.geo.get_sipms(), method)
            if self.fix_rate0 == False:
                self.n0 = 1000
            m = Minuit(self.lnlike,
                       rate0=self.n0,
                       fix_rate0=self.fix_rate0,
                       xpos=25.,
                       ypos=25.,
                       limit_rate0=(0, 1e7),
                       limit_xpos=(-150, 150),
                       limit_ypos=(-150, 150),
                       error_xpos=1.,
                       error_ypos=1.,
                       error_rate0=np.sqrt(self.n0),
                       errordef=errordef,
                       print_level=0)
            m_status = m.migrad()
            #print(m_status)
            if m_status[0].has_accurate_covar:
                # m.minos()
                m.migrad()

                fval = m_status[0].fval
                self.rate0 = m.values['rate0'] * 4 * np.pi / self.geo.a_sipm
                self.xrec = [m.values['xpos'], m.values['ypos'], 0]
                self.status = 1
            else:

                for sipm in self.geo.get_sipms():
                    print(sipm, " n = ", sipm.get_number_of_hits())

                print('m_status =', m_status[0].has_accurate_covar)
                self.rate0 = 0
                self.xrec = [-999, -999, -999]
                self.status = 0

        if method != "COG":
            self.method = "CHI2"
            chi2 = self.lnlike.__call__(rate0=self.rate0,xpos=self.xrec[0],ypos=self.xrec[1])
            self.method = method

        self.fdata = {'xr': self.xrec[0], 'yr': self.xrec[1], 'I': self.rate0, 'status': self.status,
                      'fval': fval, 'chi2': chi2, 'xgen': self.sim.get_x0()[0], 'ygen': self.sim.get_x0()[1]}

        return self.fdata

    def emulate_events(self, n_uv, n_event, **kwargs):
        """emulate_events:: Generate events and then reconstruct them
        * All UV photons are assumed to originate from the location at which they where simulated
        * The recorded number of photons on each SiPM = n_exp * n_uv with
                - nexp the number of expected photons on a SiPM / UV photon
                - n_uv the number of photons from the S2 signal
         """
        self.n_uv = n_uv

        # event display argument
        plot = kwargs.pop('plot',False)
        method = kwargs.pop('method','LNLIKE')
        nbins = kwargs.pop('nbins',15)
        plot_range = kwargs.pop('range',None)

        self.df_rec = pd.DataFrame()

        for self.i_event in range(n_event):

            if self.i_event % 100 == 0:
                print("generated ", self.i_event, " events")
            #
            # emuate one event
            #
            self.generate_hit(nuv=n_uv)
            #
            # fit the position of the emulated event
            #
            result = self.reconstruct_position(method=method)
            self.df_rec = self.df_rec.append(result, ignore_index=True)

            #
            # plot the likelihood function
            #
            if (plot):
                self.event_display(nbins=nbins,range=plot_range)
                istat = int(input("Type: 0 to quit, 1 to continue, 2 to make pdf...."))
                if  istat == 0:
                    return self.df_rec
                elif istat == 2:
                    self.generate_pdf()

                clear_output()

        # print(df)
        print("reconstruction done")
        
        print(self.df_rec)

        return self.df_rec

    def generate_pdf(self):

        fname = 'event_{0:d}.pdf'.format(self.i_event)
        self.fig.savefig(fname)

    def event_display(self, **kwargs):
        """event_display. Display of fit and log(L) or chi2 for singe events.
        Use this (long) function) to understand details of the fit procedure"""

        plot_range = kwargs.pop('range',None)
        nbins = kwargs.pop('nbins',15)
        if plot_range == 'None':
            plot_range = ((0,100),(0,100))

        print("Reconstruction::event_display() ")
        self.fig, self.ax0 = plt.subplots(nrows=1)
        self.fig.set_size_inches(10, 8)


        # draw the logL

        # make these smaller to increase the resolution
        dx, dy = 0.5, 0.5

        # generate 2 2d grids for the x & y bounds
        y, x = np.mgrid[slice(plot_range[0][0], plot_range[0][1], dy),
                        slice(plot_range[1][0], plot_range[1][1], dx)]

        z = self.lnlike.__call__(rate0=self.fdata['I'], xpos=x, ypos=y)

        z = z[:-1, :-1]
        levels = MaxNLocator(nbins=nbins).tick_values(z.min(), z.max())

        cmap = plt.get_cmap('flag')
        #norm = BoundaryNorm(levels, ncolors=cmap.N, clip=True)

        self.ax0 = self.fig.gca()

        cf = self.ax0.contourf(x[:-1, :-1] + dx / 2.,
                          y[:-1, :-1] + dy / 2., z, levels=levels,
                          cmap=cmap)
        self.fig.colorbar(cf, ax=self.ax0)
        title_string = 'Event: {0:05d}  Fit: {1:s} I0: {2:d} I0_rec: {3:d}'\
            .format(self.i_event,self.method,self.n_uv,int(self.fdata['I']))
        self.ax0.set_title(title_string)

        # add the SiPMs
        mx_eff = -1
        for sipm in self.geo.get_sipms():
            if sipm.get_number_of_hits() > mx_eff:
                mx_eff = sipm.get_number_of_hits()

        for sipm in self.geo.get_sipms():
            # draw location of SiPM
            xs = sipm.get_location()

            # plot SiPM only if in range
            if (xs[0]>plot_range[0][0]) & (xs[0]<plot_range[0][1]) & \
                    (xs[1]>plot_range[1][0]) & (xs[1]<plot_range[1][1]):

                dx = sipm.get_number_of_hits() / mx_eff * 5
                sq = plt.Rectangle(xy=(xs[0] - dx / 2, xs[1] - dx / 2),
                                   height=dx,
                                   width=dx,
                                   fill=False, color='red')
                self.ax0.add_artist(sq)
                # write number of detected photons
                txs = str(sipm.get_number_of_hits())
                plt.text(xs[0]+dx/2+2.5,xs[1],txs,color='red')


        plt.xlabel('x (mm)', fontsize=18)
        plt.ylabel('y (mm)', fontsize=18)

        # true position
        plt.plot(self.sim.get_x0()[0],self.sim.get_x0()[1],'bx',markersize=14)
        # reconstructed position
        plt.plot(self.fdata['xr'],self.fdata['yr'],'wo',markersize=14)

        plt.show()

    def plot(self, type, **kwargs):
        """Draw plots"""
        range = kwargs.pop('range', None)
        bins = kwargs.pop('bins', 100)
        # cut on the fit quality
        fcut = kwargs.pop('fcut', 99999.)

        # seect well reconstructed events
        df = self.df_rec[((self.df_rec.status == 1) & (self.df_rec.fval < fcut))]

        if type == "res":
            #
            # distributions of reconstructed position
            #
            plt.figure(figsize=(7, 5))

            # histograms with x and y positions
            plt.hist(df.xr, bins=bins, range=range)
            plt.hist(df.yr, bins=bins, range=range, alpha =0.5)
            plt.xlabel('reconstructed position (mm)')
            plt.legend(['x', 'y'])

            print("<xr> = ", df.xr.mean(), " +/-", df.xr.sem(), " mm")
            print("    rms_x = ", df.xr.std(), " mm")
            print("<yr> = ", df.yr.mean(), " +/-", df.yr.sem(), " mm")
            print("    rms_y = ", df.yr.std(), " mm")

        elif type == "xy":
            # 2D histogram with y as a function of x
            # superimposed is a outlien of a 3" PMT
            plt.figure(figsize=(8, 8))

            plt.hist2d(df.xr, df.yr, bins=(bins, bins), range=range)
            ax = plt.gca()

            mx_eff = -1
            for sipm in self.geo.get_sipms():
                if sipm.get_hit_probability() > mx_eff:
                    mx_eff = sipm.get_hit_probability()

            for sipm in self.geo.get_sipms():
                xs = sipm.get_location()
                dx = sipm.get_hit_probability() / mx_eff * 5
                sq = plt.Rectangle(xy=(xs[0] - dx / 2, xs[1] - dx / 2),
                                   height=dx,
                                   width=dx,
                                   fill=False, color='red')
                ax.add_artist(sq)

            plt.xlabel('x (mm)', fontsize=18)
            plt.ylabel('y (mm)', fontsize=18)

            plt.savefig('sipm_vs_pmt.pdf')

        elif type == "intensity":
            # reconstructed intensity
            plt.hist(df.I, bins=bins, range=range)
            plt.xlabel('$N_{UV}$ reconstructed')

            print(" N(UV) reco = ", df.I.mean(), " +/-", df.I.sem())
        elif type == "fit_quality":
            # fit quality
            plt.hist(df.fval, bins=bins, range=range)
            plt.xlabel('Fit quality')
        elif type == "test":
            #test
            plt.hist(df.xr, bins=200, range=(-25,25))
        else:
            print("Reconstruction::plot BAD plot type selected. type=", type)

        return plt.gca()
    
# -----------------------------------------------------------------------------------#
class PosFit:
    def __init__(self, sipms, method):
        self.method = method
        self.sipms = sipms
        # coordinates of the sipm
        self.xs = []
        self.ys = []
        self.zs = []
        self.err = []
        self.n = []

        for sipm in self.sipms:

            if sipm.get_number_of_hits() > -1:
                self.xs.append(sipm.get_location())
                self.n.append(sipm.get_number_of_hits())
                self.err.append(1)

    def __call__(self, rate0, xpos, ypos):
        #
        # calculate log likelihood / chi2 for position reconstruction
        #
        lnlike = 0

        for i in range(len(self.n)):
            #
            # calculate the number of expected photons
            #
            nexpected = self.nexp(rate0, xpos, ypos, i)
            #
            # number of oserved events
            #
            N = self.n[i]


            if self.method == "CHI2":
                res = self.n[i] - nexpected
                # lnlike = lnlike+res*res / (self.err[i]*self.err[i])
                #if nexpected > 1e-6:
                lnlike = lnlike + res * res / nexpected
                #lnlike = lnlike + res * res / self.n[i]


                #if self.n[i] > 0:
                #   lnlike = lnlike + res * res / self.nexp
                #else:
                #    lnlike = lnlike + res * res / self.nexp

            elif self.method == "LNLIKE":

                if (N < 100):  # exact calculation
                    ln_nfac = np.log(1. * np.math.factorial(N))
                else:  # Stirling approximation for large N
                    ln_nfac = N * np.log(1. * N) - N

                lnp = -nexpected + N * np.log(nexpected) - ln_nfac

                lnlike = lnlike - lnp
            else:
                print("PosRec::BAD METHOD for position reconstruction. method =", self.method)

        return lnlike

    def nexp(self, rate0, xpos, ypos, i):
        """Calculate the expected number of photons hitting a SiPM"""

        xfit = np.array([xpos,ypos,0])
        delta = np.array(self.xs[i]) - xfit

        dist = np.linalg.norm(delta)
        dist2 = dist**2

        # correct for the slid angle of the sensor
        cost = abs(np.dot(delta, self.sipms[i].get_normal_vector())/dist)

        # quantum efficiency
        qe = self.sipms[i].qe

        # expected number of events
        yy = rate0 / dist2 * cost * qe
        return yy

# -----------------------------------------------------------------------------------#
class Analysis:  
    """plot data over multiple locations"""
    
    def __init__(self, recs, xsize, ysize):
        self.recs = recs
        self.rec1 = recs[0]
        self.sim1 = self.rec1.sim
        self.geo1 = self.rec1.sim.geo
        #number of bins of x,y in simulation class
        self.xsize = xsize
        self.ysize = ysize

    def merge(self):
        """store relevant data from reconstructions by looping over dataframes from each reconstruction and saving information in np arrays"""
        
        #create numpy arrays to fill with data while looping over reconstructions
               #possibly make into one big np array: posities = np.zeros(hoeveel events , dtype=[('xmeans',np.float),('ygens',np.float)
        self.xdif = np.zeros((self.ysize, self.xsize))
        self.ydif = np.zeros((self.ysize, self.xsize))
        self.rdif = np.zeros((self.ysize, self.xsize))
        self.phidif = np.zeros((self.ysize, self.xsize))
        self.xsig = np.zeros((self.ysize, self.xsize))
        self.ysig = np.zeros((self.ysize, self.xsize))
        self.rsig = np.zeros((self.ysize, self.xsize))
        self.phisig = np.zeros((self.ysize, self.xsize))
        self.xgens = np.zeros((self.xsize))
        self.ygens = np.zeros((self.ysize))

        #i,j keep track of x,y generated positions respectively; ugly but possible to do so as long as there is a y-loop in an x-loop while generating with Simulator
        i=0
        j=0
        #fill numpy arrays
        for rec in self.recs:
            self.xgens[i] = round(rec.sim.get_x0()[0],1)
            self.ygens[j] = round(rec.sim.get_x0()[1],1)            
            self.xdif[j,i] = rec.df_rec.xr.mean()-rec.sim.get_x0()[0]
            self.ydif[j,i] = rec.df_rec.yr.mean()-rec.sim.get_x0()[1]
            self.xsig[j,i] = rec.df_rec.xr.sem()
            self.ysig[j,i] = rec.df_rec.yr.sem()            
            self.rdif[j,i] = (rec.df_rec.xr.mean()**2+rec.df_rec.yr.mean()**2)**0.5-(rec.sim.get_x0()[0]**2+rec.sim.get_x0()[1]**2)**0.5
            self.rsig[j,i] = (rec.df_rec.xr.sem()**2+rec.df_rec.yr.sem()**2)**0.5
            if rec.df_rec.xr.mean()and rec.sim.get_x0()[0]!= 0:
                self.phidif[j,i] = np.arctan(rec.df_rec.yr.mean()/rec.df_rec.xr.mean())-np.arctan(rec.sim.get_x0()[1]/rec.sim.get_x0()[0])   
            else:
                self.phidif[j,i] = 0
            if rec.df_rec.xr.sem()!= 0:
                self.phisig[j,i] = np.arctan(rec.df_rec.yr.sem()/rec.df_rec.xr.sem()) 
            else:
                self.phisig[j,i] = 0
            
            j+=1
            if j == self.ysize:
                i +=1
                j = 0
        
        return self.xgens, self.ygens, self.xdif, self.ydif, self.rdif, self.phidif, self.xsig, self.ysig, self.rsig, self.phisig
    
    
    def plot2d(self, type, cmap):
        #plots two types of two dimensional 'heatmaps': difference between generated and reconstructed value and sigma of x,y,r and phi; change any inputs here, actual plotting happens in function "plot2dgeneral"
        
        
        if type == "xdif":
            
            self.plot2dgeneral(data=self.xdif, type=type, title="Reconstructed - generated x-position", cbarlabel='<Rec-Gen> (mm)', cmap=cmap)
            
        elif type == "ydif":

            self.plot2dgeneral(data=self.ydif, type=type, title="Reconstructed - generated y-position", cbarlabel='<Rec-Gen> (mm)', cmap=cmap)
            
        elif type == "rdif":

            self.plot2dgeneral(data=self.rdif, type=type, title="Reconstructed - generated r-position", cbarlabel='<Rec-Gen> (mm)', cmap=cmap)
            
        elif type == "phidif":

            self.plot2dgeneral(data=self.phidif, type=type, title="Reconstructed - generated phi-position", cbarlabel='<Rec-Gen> (radians)', cmap=cmap)
            
        elif type == "xsig":
        
            self.plot2dgeneral(data=self.xsig, type=type, title="Standard deviation on reconstructed x-position", cbarlabel='$\sigma$ on x (mm)', cmap=cmap)

        elif type == "ysig":

            self.plot2dgeneral(data=self.ysig, type=type, title="Standard deviation on reconstructed y-position", cbarlabel='$\sigma$ on y (mm)', cmap=cmap)
                            
        elif type == "rsig":
        
            self.plot2dgeneral(data=self.rsig, type=type, title="Standard deviation on reconstructed r-position", cbarlabel='$\sigma$ on r (mm)', cmap=cmap)   
            
        elif type == "phisig":

            self.plot2dgeneral(data=self.phisig, type=type, title="Standard deviation on reconstructed phi-position", cbarlabel='$\sigma$ on phi (radians)', cmap=cmap)
                            
        else:
            print("Analysis::plot BAD plot type selected. type=", type)
     
            
    def plot2dgeneral(self, data, type, **kwargs):
       
        #create plot and axes
        fig, ax = plt.subplots()
        ax.set_xticks(np.arange(len(self.xgens)))
        ax.set_yticks(np.arange(len(self.ygens)))
        ax.set_xticklabels(self.xgens)
        ax.set_yticklabels(self.ygens)
        ax.set_xlabel("generated x-position")
        ax.set_ylabel("generated y-position")
        plt.setp(ax.get_xticklabels(), rotation=90, ha="right",
         rotation_mode="anchor")
        
        #kwargs
        title = kwargs.pop('title', None)
        cbarlabel = kwargs.pop('cbarlabel', None)
        cmap = kwargs.pop('cmap', 'Blues')
        
        
        #set colourbar boundaries
        if type == "xdif" or type == "ydif" or type == "rdif":
            bound_upper =  max(abs(self.xdif.max()), abs(self.xdif.min()), abs(self.ydif.max()), abs(self.ydif.min()), abs(self.rdif.max()), abs(self.rdif.min())) 
            bound_lower = -bound_upper
            
        elif type == "xsig" or type == "ysig" or type == "rsig":
            bound_upper = max(abs(self.xsig.max()), abs(self.ysig.max()), abs(self.rsig.max()))
            bound_lower = 0
            
        elif type =="phidif":
            bound_upper = max(abs(self.phidif.max()), abs(self.phidif.min()))
            bound_lower = -bound_upper
            
        elif type =="phisig":
            bound_upper = max(abs(self.phisig.max()), abs(self.phisig.min()))
            bound_lower = 0
            
        #fill plot
        im = ax.imshow(data, cmap = cmap, vmin=bound_lower, vmax=bound_upper)
        ax.set_title(title)
        
        #create colourbar
        cbar = ax.figure.colorbar(im, ax=ax)
        #annoying; this type of plot plots first y-value on top, so y-axis needs to be reversed
        ax.invert_yaxis()
        
        #set colourbar label
        cbar.ax.set_ylabel(cbarlabel, rotation=-90, va="bottom")       
            
            
    def plot(self, type, bins, range):
        #Plot 1d histograms of <Rec-Gen> and sigma for x,y,r and phi, to compare averages and spread
        
        if type == "xydif":
            
            self.plotgeneral(bins, range, data_1=self.xdif.flatten(), data_2=self.ydif.flatten(), title='Histogram of <Rec-Gen> for x,y', xlabel = '<Rec-Gen> (mm)', legend = ['x', 'y'])
            
        elif type == "xysig":
            
            self.plotgeneral(bins, range, data_1=self.xsig.flatten(), data_2=self.ysig.flatten(), title='Histogram of standard dev. of x,y', xlabel = 'sigma (mm)', legend = ['x', 'y'])
            
        elif type == "rdif":
            
            self.plotgeneral(bins, range, data_1=self.rdif.flatten(), title='Histogram of <Rec-Gen> for r', xlabel = '<Rec-Gen> (mm)', legend = ['r'])
            
        elif type == "rsig":
            
            self.plotgeneral(bins, range, data_1=self.rsig.flatten(), title='Histogram of standard dev. of r', xlabel = 'sigma (mm)', legend = ['r'])
            
        elif type == "phidif":
            
            self.plotgeneral(bins, range, data_1=self.phidif.flatten(), title='Histogram of <Rec-Gen> for phi', xlabel = '<Rec-Gen> (radians)', legend = ['phi'])
            
        elif type == "phisig":
            
            self.plotgeneral(bins, range, data_1=self.phisig.flatten(), title='Histogram of standard dev. for phi', xlabel = 'sigma (radians)', legend = ['phi'])
            
        else:
            print("Analysis::plot BAD plot type selected. type=", type)
        
        return plt.gca()
                
    def plotgeneral(self, bins, range, data_1, **kwargs):
        #does plotting for plot function
        
        plt.figure(figsize=(7, 5))
        
        plt.hist(data_1, bins=bins, range=range)
        data_2 = kwargs.pop('data_2', False)
        if type(data_2) !=  bool:
            plt.hist(data_2, bins=bins, range=range, alpha=0.5)
                 
        title = kwargs.pop('title', None)
        xlabel = kwargs.pop('xlabel', None)
        legend = kwargs.pop('legend', None)
        plt.title(title)
        plt.xlabel(xlabel)
        plt.legend(legend)
                 
        return plt.gca()
            
