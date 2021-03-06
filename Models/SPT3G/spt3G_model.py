from numpy import  array,  log, dot, exp, zeros, errstate,shape, hstack
from Models.Foregrounds.spt3G_foregrounds import foregrounds
from collections import OrderedDict



class spt3G_model():
    '''
    Class for spt3G model. So far not very different than the planck model. Initialize with spectra, ell range, and bin size to     be used
    '''
    
    def __init__(self, model='classy',
                 specrange = [('TT',(50,3000)),
                                ('EE',(50,5000)),
                                ('TE',(50,5000))],
                 bin_size = 5):
        '''
        specrange: list of tuples ('TT',slice(2,3000)) that indicate the spectra to be included in the model
        and a slice to determine the ell range. Spectra must be in the same order as the covariance you plan on using
        with this model.
        '''
        self.order = [i[0] for i in specrange] #Keeps the order of the spectra to be returned
        self.windowrange = {k:slice(v[0],v[1])for k,v in specrange}
        
        #Top hat window functions
        self.windows =  {k:array([self.top_hat(l,v,bin_size) 
                               for l in range(v.start+bin_size//2,v.stop+1-max(1,bin_size//2),bin_size)]) 
                               for k,v in self.windowrange.items()}
        
        #Maximum number of bins for a spectrum. Will need to pad the array with zeros to keep the same shape as 
        #the covaraince
        self.numbins = max([shape(self.windows[k])[0] for k in self.windows.keys()]) 
        
        #Instance of camb and foreground model used to calculate model
        if model == 'classy': 
            from Models.CMB.Fisher_classy import model 
        elif model == 'camb': 
            from Models.CMB.Fisher_camb import model
        else:
            raise ValueError('models other than camb or classy not implemented')    
        self.cmb=model()
        self.foregrounds=foregrounds()
        
    def __call__(self,**params):
        '''
        Params: dictionary of parameters needed to calculate model
        Fisher_CMB.py plugs parameters in here to do calculation
        '''
        cmb,foregrounds,cals=self.get_cmb_fgs_and_cals(params)
        
        '''
        Apply window functions and return a single array of Dbs in order, padded with zeros to fit sqaure matrix.
        To be used with block covariance that is broken up by spectra (might change to break things up by ell instead
        but this is easier and Fisher_matrix.py does not take advantage of block diagonal matrices, and this format is
        easier for testing purposes).
        '''
        full_dbs=[]
        #Currently not including aberration
        for k in self.order:
            dbs=zeros(self.numbins)
            dls = cals.get(k,1)*(cmb[k][self.windowrange[k]]+foregrounds.get(k,zeros(len(cmb[k])))[self.windowrange[k]])
            #dls[k] *= self.aberration(dls[k])
            dbs[:shape(self.windows[k])[0]] = dot(self.windows[k],dls)
            full_dbs=hstack([full_dbs,dbs])
        return full_dbs
    
    def get_cmb_fgs_and_cals(self,params):
        #Need to convert some params to camb friendly form
        if params.get('clamp',None) is not None: 
            params['As']=params['clamp']*exp(2*params.get('tau',.07))*1e-9
            params.pop('clamp',[])
        if params.get('ommh2',None) is not None: 
            params['omch2']=params['ommh2']-params.get('ombh2',.02227)
            params.pop('ommh2',[])
        params['spectra'] = self.windows.keys()
        foregrounds = self.foregrounds(**params)
        cals = {'TT':1/params.get('Tcal',1)**2,
                'TE':1/(params.get('Tcal',1)**(2)*params.get('Pcal',1)),
                'EE':1/((params.get('Tcal',1)**(2)*params.get('Pcal',1)**(2)))}
        params.pop('Tcal',[])
        params.pop('Pcal',[])
        params.pop('Asz',[])
        params.pop('Acib',[])
        params.pop('A_TEps',[])
        params.pop('Aps',[])
        #Calculate model for current params
        cmb = self.cmb(**params)
        return (cmb,foregrounds,cals)
    
    def top_hat(self,loc,win_range,binn):
        '''
        Returns a top hat function centered on loc with range= win_range and bin size = binn.
        '''
        th = zeros(win_range.stop+1)
        th[int(loc-binn//2):int(loc+binn//2+binn%2)]+=(1/binn)
        return th[win_range]
    
    def aberration(self,y):
        '''
        Calculates aberration correction assuming SPT-SZ field center.
        '''
        with errstate(divide='ignore'):
            x = arange(self.windowrange.start,self.windowrange.stop)
            lnx=log(x)
            lny=log(y*2*pi/(x*(x+1)))
            return 1+.26*1.23e-3*array([0]+[(lny[i+1]-lny[i])/(lnx[i+1]-lnx[i]) for i in arange(len(y)-1)])
    
