import scipy.signal as signal
import scipy.optimize as optimize
import scipy.integrate as integrate
import matplotlib.pyplot as plt
import numpy as np
import scipy.special as special
from pyhht.visualization import plot_imfs   # Hilbert-Huang TF analysis
from pyhht import EMD                       # Hilbert-Huang TF analysis
import rftool.utility as util
import pywt # CWT


def Albersheim( Pfa, Pd, N ):
    """
    Calculate required SNR for non-coherent integration over N pulses, by use of Albersheims equation.

    Pd is the probability of detection (linear)
    Pfa is the probability of false alarm (linear)
    N is the number of non-coherently integrated pulses
    Returns SNR in dB

    Accurate within 0.2 dB for:
    10^-7   <  Pfa  < 10^-3
    0.1     <  Pd   < 0.9
    1       <= N    < 8096
    - M. A. Richards and J. A. Scheer and W. A. Holm, Principles of Modern Radar, SciTech Publishing, 2010 
    """

    A = np.log(np.divide(0.62, Pfa))
    B = np.log(np.divide(Pd,1-Pd))
    SNRdB = -5*np.log10(N)+(6.2+np.divide(4.54, np.sqrt(N+0.44)))*np.log10(A+(0.12*A*B)+(0.7*B))
    return SNRdB

def Shnidman( Pfa, Pd, N, SW ):
    """
    Calculate required SNR for non-coherent integration over N pulses for swerling cases, by use of Shnidman equation.

    Pd is the probability of detection (linear)
    Pfa is the probability of false alarm (linear)
    N is the number of non-coherently integrated pulses
    SW is the swerling model: 0-4 (zero is non-swerling)
    Returns SNR in dB

    Accurate within 1 dB for:
    10^-7   <  Pfa  < 10^-3
    0.1     <= Pd   =< 0.99*10^-9
    1       <= N    < 100
    - M. A. Richards and J. A. Scheer and W. A. Holm, Principles of Modern Radar, SciTech Publishing, 2010 
    """
    C = 0
    alpha = 0

    if N < 40:
        alpha = 0
    elif N > 40:
        alpha = np.divide(1,4)
    
    eta = np.sqrt( -0.8*np.log(4*Pfa*(1-Pfa)) ) + np.sign(Pd-0.5)*np.sqrt( -0.8*np.log(4*Pd*(1-Pd)) )

    X_inf = eta*( eta + 2*np.sqrt( np.divide(N,2)+(alpha-np.divide(1,4)) ) )

    if SW==0:   # Non swerling case
        C = 1
    else:       # Swerling case
        def K(SW):
            if  SW==1:
                K = 1
            elif  SW==2:
                K = N
            elif  SW==3:
                2
            else:
                K = 2*N

        C1 = np.divide( ( (17.7006*Pd-18.4496)*Pd+14.5339 )*Pd-3.525, K(SW) )
        C2 = np.divide(1,K(SW))*( np.exp( 27.31*Pd-25.14 ) + (Pd-0.8)*( 0.7*np.log( np.divide(10e-5, Pfa) ) + np.divide( 2*N-20, 80 ) ) )
        CdB = 0
        if Pd < 0.8872:
            CdB = C1
        elif Pd > 0.99:
            CdB = C1 + C2
        
        C = np.power(10, np.divide(CdB,10) )
    
    X1= np.divide(C*X_inf, N)
    
    SNRdB = 10*np.log10(X1)
    return SNRdB

def upconvert( sig, f_c, Fs=1 ):
    """
    Upconvert baseband waveform to IF
    f_c is the IF center frequency
    Fs is the sample frequency
    """
    a = np.linspace(0, sig.shape[0]-1, sig.shape[0])
    # Angular increments per sample times sample number
    phi_j = 2*np.pi*np.divide(f_c,Fs)*a
    # Complex IF carrier
    sig = np.multiply(sig, np.exp(1j*phi_j))
    return sig

def hilbert_spectrum( sig, Fs=1 ):
    """
    Hilbert-Huang transform with Hilbert spectral plot.
    The plot neglects negative frequencies.
    
    sig is a time series
    Fs is the sample frequency

    Based on:
    - S.E. Hamdi et al., Hilbert-Huang Transform versus Fourier based analysis for diffused ultrasonic waves structural health monitoring in polymer based composite materials,Proceedings of the Acoustics 2012 Nantes Conference.
    """
    # Hilbert-Huang
    decomposer = EMD(sig)
    imfs = decomposer.decompose()

    imfAngle = np.angle(signal.hilbert(imfs))
    dt = np.divide(1,Fs)
    
    t = np.linspace(0, (sig.shape[0]-1)*dt, sig.shape[0])

    # Calculate instantaneous frequency
    instFreq = np.divide(np.gradient(imfAngle,t,axis=1), 2*np.pi)
    """
    There is an image of the instantaneous frequency response occuring at -Fs/2. THis is currently not shown in the plot. 
    """

    # Calculate Hilbert spectrum
    # Time, frequency, magnitude
    intensity = np.absolute(signal.hilbert(imfs))
    plt.figure()
    for i in range(np.size(instFreq,0)):
        plt.scatter(t, instFreq[i], c=intensity[i], s=5, alpha=0.3)

    plt.title("Hilbert Spectrum")
    plt.xlabel('t [s]')
    plt.ylabel('f [Hz]')
    plt.ylim(0,np.divide(Fs,2))
    plt.xlim(t[1], t[-1])
    plt.tight_layout()

def ACF(x, plot = True):
    """
    Normalized autocorrelation Function of input x.
    x is the signal being analyzed. If x is a matrix, the correlation is performed columnwise.
    plot decides wether to plot the result.

    The output is 2*len(x)-1 long. If the input is a matrix, the output is a matrix.
    """
    # If x is a vector, ensure it is a column vector.
    if x.ndim < 1:
        x = np.expand_dims(x, axis=1)

    # Iterate through columns
    r_xx = np.empty( shape=[2*np.size(x,0)-1, np.size(x,1)] )
    for n in range(0, np.size(x,1)):
        r_xx[:,n] = np.correlate(x[:,n], x[:,n], mode='full')
        
    if plot == True:
        # Plot
        plt.figure()
        
        for column in r_xx.T:
            # Normalize
            column = np.absolute(column / abs(column).max())
            plt.plot(util.mag2db(column))

        yMin = np.maximum(-100, np.min(r_xx))
        plt.ylim([yMin, 0])
        plt.title("Autocorrelation Function")
        plt.ylabel("Normalized magnitude [dB]")
        plt.tight_layout()
    return r_xx

# TODO def AF(x, Fs=1, doppler = 2)
    """
    Ambuigity Function
    x is the signal being analyzed.
    Fs is the sampling frequency of the signal x [Hz].
    doppler is the max doppler shift in Hz
    """

class chirp:
    """
    Object for generating linear and non-linear chirps.
    """
    c = np.array([1,1,1])
    # FFT lenth for computation og magnitude spectrum.
    fftLen = 2048

    class target:
        """
        Object for storing the properties of the target chirp. Used in optimization aproach for coefficients.
        """

        def __init__( self,  r_xx_dB=1, f=1, order=8):
            self.r_xx_dB = r_xx_dB
            self.f = f
            self.order = order

    def __init__( self, Fs=1 ):
        """
        t_i is the chirp duration [s].
        Fs is the intended sampling frequency [Hz]. Fs must be at last twice the highest frequency in the input PSD. If Fs < 2*max(f), then Fs = 2*max(f)
        """
        self.Fs = Fs

    def checkSampleRate(self):
        """
        Check that the sample rate is within the nyquist criterion. I.e . that no phase difference between two consecutive samples exceeds pi.
        """
        errorVecotr = np.abs(np.gradient(self.targetOmega_t)*2*np.pi)-np.pi

        if 0 < np.max(errorVecotr):
            print("Warning, sample rate too low. Maximum phase change is", np.pi+np.max(errorVecotr), "Maximum allowed is pi." )
    
    def generate( self ):
        """
        Generate Non.Linear Frequency Modualted (NLFM) chirps based on a polynomial of arbitrary order.

        t is the length of the chirp [s]
        c is a vector of phase polynomial coefficients (arbitrary length)
        Fs is the sampling frequency [Hz]

        c[0] is the reference phase
        c[1] is the reference frequency,
        c[2] is the nominal constant chirp rate
        
        For symmetricsl PSD; c_n = 0 for odd n > 2, that is, for n = 3, 5, 7,…

        - A .W. Doerry, Generating Nonlinear FM Chirp Waveforms for Radar, Sandia National Laboratories, 2006
        """
        dt = 1/self.Fs        # seconds
        #self.t = np.linspace(-self.T/2, (self.T/2)-dt, np.intc(self.Fs*self.T))  # Time vector

        """
        phi_t = 0
        for n in range(0, len(self.c)):
            loopVar = self.c[n]/special.factorial(n)
            phi_t = phi_t+np.power(self.t, n)*loopVar

        self.phi_t = phi_t"""
        #stretchedOmega_t = signal.resample(self.targetOmega_t, len(self.t))

        
        phi_t = util.indefIntegration( self.targetOmega_t, dt )
        sig = np.exp(np.multiply(1j*2*np.pi, phi_t))
        return sig

    def getInstFreq(self, analytical=True, plot=True):
        if analytical == True:
            # Calculate the instantaneous frequency based on polynoimial coefficients.
            omega_t = 0
            for n in range(1, len(self.c)):
                loopVar = self.c[n]/special.factorial(n-1)
                omega_t = omega_t+np.power(self.t, n-1)*loopVar

        else:
            # Calculate the instantaneous frequency based on phase vector.
            omega_t = np.gradient(self.phi_t, self.t)

        if plot == True:
            plt.figure()
            plt.plot(self.t, omega_t)
            plt.plot(self.t, self.targetOmega_t)
            plt.xlabel('t [s]')
            plt.ylabel('f [Hz]')
            plt.title("Instantaneous Frequency")
            plt.show()
        return omega_t

    def getChirpRate(self, analytical=True, plot=True):
        if analytical == True:
            # Calculate the chirp rate based on polynoimial coefficients.
            gamma_t = 0
            for n in range(2, len(self.c)):
                loopVar = self.c[n]/special.factorial(n-2)
                gamma_t = gamma_t+np.power(self.t,n-2)*loopVar
        else:
            # Calculate the chirp rate based on phase vector.
            gamma_t = np.gradient(self.getInstFreq(plot=False), self.t)

        if plot == True:
            plt.figure()
            plt.plot(self.t, gamma_t)
            plt.xlabel('t [s]')
            plt.ylabel('f [Hz]')
            plt.title("Chirp Rate")
            plt.show()
        return gamma_t

    def plotMagnitude( self, sig_t ):
        sig_f = np.fft.fft(sig_t, self.fftLen)/self.fftLen
        # Shift and normalize.
        sig_f = np.abs(np.fft.fftshift(sig_f / abs(sig_f).max()))
        # Remove infinitesimally small components.
        sig_f = util.mag2db(np.maximum(sig_f, 1e-10))
        f = np.linspace(-self.Fs/2, self.Fs/2, len(sig_f))
        plt.figure()
        plt.plot(f, sig_f)
        plt.xlim([-self.Fs/2, self.Fs/2])
        plt.title("Frequency response")
        plt.ylabel("Normalized magnitude [dB]")
        plt.xlabel("Frequency [Hz]")
        plt.show()

    def CWT( self, plot=False ):
        """
        Calculates Continious Wavelet Transform.
        """
        print("Calculating CWT")
        coef, freqs=pywt.cwt(self.sig, np.arange(self.Fs/4,self.Fs/2, 64),'cmor1.5-1.0')
        
        if plot == True:
            plt.matshow(coef)
            plt.show()
        return coef

    def PSD( self, sig_t, plot=False ):
        """
        Calculates Power Spectral Density in dBW/Hz.
        """
        f, psd = signal.welch(sig_t, fs=self.Fs, nfft=self.fftLen, nperseg=self.fftLen, window = signal.blackmanharris(self.fftLen),
        noverlap = self.fftLen/4, return_onesided=False)

        if plot == True:
            #f = np.linspace(-self.Fs/2, self.Fs/2, len(psd))
            # Remove infinitesimally small components
            #psd_dB = util.pow2db(np.maximum(psd, 1e-14))
            psd_dB = util.pow2db(psd)
            plt.plot(f, psd_dB)
            plt.title("Welch's PSD Estimate")
            plt.ylabel("dBW/Hz")
            plt.xlabel("Frequency [Hz]")
            plt.show()
        return psd

    def ACFdB( self, sig_t, plot=False, shift=False ):
        """
        Calculates normalized ACF in dB based on FFT downsampling.
        sig_t is the time-domain input signal.
        plot specifies whether to plot the function.
        Shift specifies whether to use convolution (True), or IFFT(PSD(sig)) (False)
        """
        r_xx = np.array([1])
        if shift == True:
            r_xx = signal.correlate(sig_t, sig_t)
            r_xx = abs(r_xx)/abs(r_xx).max()

        else:
            psd = self.PSD(sig_t)
            r_xx = np.fft.ifft(psd, self.fftLen)# ifft is scaled by 1/n
            # Shift and normalize
            r_xx = np.abs(np.fft.fftshift(r_xx))/abs(r_xx).max()
        
        r_xx_dB = util.mag2db( r_xx )

        if plot == True:
            # Remove infinitesimally small components
            plt.figure()
            plt.plot(r_xx_dB)
            plt.title("ACF")
            plt.ylabel("Normalized Magnitude [dB]")
            plt.xlabel("Delay")
            plt.show()
        return r_xx_dB

    def W( self, omega ):
        """
        Lookup table for the W function. Takes instantaneous frequency as input.
        """
        delta_omega_W = self.omega_W[1]-self.omega_W[0]

        W_omega = np.empty((len(omega)))
        for i in range(0, len(omega)):
            index = np.intc(omega[i]/delta_omega_W)+np.intc(len(self.window)/2)
            if index<0:
                index = 0
            elif len(self.window)-1<index:
                index = len(self.window)-1

            W_omega[i] = self.window[index]
        return W_omega

    def gamma_t_objective( self, scale ):
        """
        Objective function for finding gamma_t that meets the constraints.
        scale scales the gamma function.
        """
        self.iterationCount = self.iterationCount +1
        if self.iterationCount % 10 == 0:
            print("Iteration",self.iterationCount)
        

        # Calculate gamma_t for this iteration
        self.gamma_t = self.gamma_t_initial*scale

        # omega_t = integrate.cumtrapz(self.gamma_t, x =self.t ) # resulthas one less cell
        omega_t = np.cumsum(self.gamma_t)*self.dt # Ghetto integral
        # Place center frequency at omega_0
        omega_t = omega_t + (self.omega_0 - omega_t[np.intc(len(omega_t)/2)])
        
        # Scale W function to enclose omega_t
        self.omega_W = np.linspace(omega_t[0]-self.omega_0, omega_t[-1]-self.omega_0, len(self.window))

        # Calculate NLFM gamma function
        self.gamma_t = self.gamma_t[np.intc(len(self.gamma_t)/2)]/self.W(omega_t-self.omega_0)
        self.targetOmega_t = util.indefIntegration(self.gamma_t, self.dt)
        self.targetOmega_t = self.targetOmega_t  + (self.omega_0 - self.targetOmega_t[np.intc(len(self.targetOmega_t)/2)])

        OmegaIteration = np.trapz(self.gamma_t, dx=self.dt)
        cost = np.abs(self.Omega - OmegaIteration)
        return cost

    def setCoefficients( self, c ):
        # For symmetricsl PSD; cn = 0 for odd n > 2, that is, for n = 3, 5, 7, …
        # Nulling out these coefficients
        if (self.target.symm == True) and (len(c) > 3):
            for i in range(3, len(c)):
                if (i % 2) == 1:
                    c[i]=0
        self.c = c

    def coefficient_objective( self, coefficients ):
        """
        Objective function for finding coefficients that meet the gamma_t Function.
        """

        self.setCoefficients(coefficients)
        optOmega_t = self.getInstFreq(plot = False)
        error = np.abs(self.targetOmega_t - optOmega_t)
        cost = np.sum(np.power(error, 2))
        """
        if (self.iterationCount % 1000) == 0:
            plt.figure()
            plt.plot(self.t, optOmega_t)
            plt.show()
        """

        self.iterationCount = self.iterationCount +1
        print("Iteration",self.iterationCount, "cost =", cost)
        return cost
        
    def getCoefficients( self, window, symm, T=1e-3, targetBw=10e3, centerFreq=20e3, order=8):
        """
        Calculate the necessary coefficients in order to generate a NLFM chirp with a specific magnitude envelope (in frequency domain). Chirp generated using rftool.radar.generate().
        Coefficients are found through non-linear optimization.

        Window_ is the window function for the target PSD. It is used as a LUT based function from -Omega/2 to Omega/2, where Omega=targetBw.
        symm configures wether the intend PSD should be symmetrical. With a symmetrical target PSD, the result will be close to symmetrical even with symm set to false, 
        however the dimentionality of the problem is reduced greatly by setting symm to True.
        T is the pulse duration [s].
        targetBw is the taget bandwidth of the chirp [Hz].
        centerFreq is the center frequency of the chirp [Hz].
        order is the oder of the phase polynomial used to generate the chirp frequency characteristics [integer].
        pints is the number of points used t evaluate the chirp function. Not to be confused with the number of samples in the genrerated IF chirp.
        """
        #self.fftLen = len(r_xx_dB) # Legacy

        self.Omega = targetBw
        print("self.Omega", self.Omega)
        self.window = window
        self.window = np.maximum(window, 1e-8)

        
        plt.figure()
        plt.plot(self.window)
        plt.title("Target Window")
        plt.show()
        

        self.omega_0 = centerFreq
        self.T = T
        self.points = np.intc(self.Fs*T)
        #self.ponts = points
        self.t = np.linspace(-self.T/2, self.T/2, self.points)
        self.dt = self.T/(self.points-1)
        self.target.symm = symm

        # optimization routine
        # Count iterations
        self.iterationCount = 0

        # Calculate LFM chirp rate (initial gamma_t)
        self.gamma_t_initial = np.full(self.points, self.Omega/self.T)

        # Initial scaling
        p0=np.array([1])
        # Optimize gamma_t curve with window
        chirpOpt = optimize.minimize(self.gamma_t_objective, p0, method='L-BFGS-B')
        
        plt.figure()
        plt.plot(self.t, self.gamma_t)
        plt.title("gamma_t")
        plt.figure()
        plt.plot(self.t, self.targetOmega_t)
        plt.title("targetOmega_t")
        plt.show()

        """
        # optimization routine
        # Count iterations
        self.iterationCount = 0
        
        Initial Values, for LFM:
        c[0] is the reference phases
        c[1] is the reference frequency
        c[2] is the nominal constant chirp rate
        
        c0 = np.zeros( order )
        c0[1] = self.omega_0
        c0[2] = self.Omega/self.T     # Initial chirp rate
        
        print("Initiating optimization routine")
        minimizer_kwargs = {"method": "BFGS"}
        #coefOpt = optimize.basinhopping(self.coefficient_objective, c0, niter=1000, minimizer_kwargs=minimizer_kwargs, niter_success =100)
        
        bounds = [(-1e6, 1e6), (-1e6, 1e6), (-1e6, 1e6), (-1e6, 1e6), (-1e6, 1e6), (-1e6, 1e6), (-1e6, 1e6), (-1e6, 1e6)]
        optimize.differential_evolution(self.coefficient_objective, bounds, popsize = np.intc(1e3))
    

        #coefOpt = optimize.minimize(self.coefficient_objective, x0=c0)

        # development stuff
        self.getChirpRate()
        self.getInstFreq()
        """
        self.sig = self.generate()
        #self.CWT(plot = True)
        return self.c