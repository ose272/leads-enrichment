import csv
import re
from urllib.parse import urlparse

input_file = 'c:/Users/HP/Downloads/leads_1_cleaned.csv'
output_file = 'c:/Users/HP/Desktop/AUTOMATION 1/leads_for_ingest.csv'

def extract_phone(snippet):
    if not snippet:
        return ''
    patterns = [
        r'\(\d{3}\)\s*\d{3}[-\s]?\d{4}',
        r'\d{3}[-\s]\d{3}[-\s]\d{4}',
        r'\d{10}',
    ]
    for pattern in patterns:
        match = re.search(pattern, snippet)
        if match:
            return match.group()
    return ''

def is_valid_company_website(url):
    if not url or not url.startswith('http'):
        return False

    parsed = urlparse(url)
    domain = parsed.netloc.lower().replace('www.', '')
    path = parsed.path.lower()

    skip_domains = [
        'yelp.com', 'diamondcertified.org', 'downtobid.com', 'datasetlabs.ai',
        'trane.com', 'bryant.com', 'indeed.com', 'instagram.com', 'mapquest.com',
        'angi.com', 'homeadvisor.com', 'ziprecruiter.com', 'linkedin.com',
        'reddit.com', 'youtube.com', 'einpresswire.com', 'prnewswire.com',
        'nhregister.com', 'timesunion.com', 'yakimaherald.com', 'wric.com',
        '12onyourside.com', 'sfchronicle.com', 'sfgate.com', 'serviceagent.ai',
        'facebook.com', 'twitter.com', 'google.com', 'bing.com', 'search.',
        'jobcorps.gov', 'abcnews4.com', 'alaska.uhire.com', 'acrepairnearyou.net',
        'usaheatingcontractors.com', 'nbcnews.com', 'cbsnews.com',
        'maptons.com', 'cybo.com', 'np.maptons.com', 'biashara.cybo.com',
        'amerenillinoissavings.com', 'alaskadefense.com', 'alaskarefrigeration.ca',
        'alaskastructures.com', 'allairshomeservices.com', 'atlasheat.com',
        'bardi.com', 'bigboyhvac.com', 'careers.acehardware.com', 'careers.aldi.us',
        'cars.superpages.com', 'catalog.uaa.alaska.edu', 'chartercollege.edu',
        'comfortsystemsusa.com', 'csspe.ca', 'daikincomfort.com', 'buildermuse.com',
        'cumming-ga.kempenheatingandac.com', 'daikinapplied.com', 'aaon.com',
        'samsunghvac.com', 'lennox.com', 'york.com', 'rheem.com', 'carrier.com',
        'modine.com', 'captiveaire.com', 'pacificcoasttrane.com', 'glassdoor.com',
        'simplyhired.com', 'jobs.johnsoncontrols.com', 'disneycareers.com',
        'main.hercjobs.org', 'operationhomefront.org', 'ncees.org', 'psiexams.com',
        'pearsonvue.com', 'hvacschoolsguide.com', 'waze.com', 'local.yahoo.com',
        'sf.gov', 'commerce.alaska.gov', 'alaska.edu', 'ualocal38.org',
        'ashrae.org', 'cheers.org', 'discountmechanical.net', 'betterbuyer.com',
        'procalcs.net', 'provexam.com', 'hvacservicehub.com', 'alaskabusinessesnearme.com',
        'hvacalaska.mil.tf', 'alaskahvacauthority.com', 'diamondheatingalaska.com',
        'heatwavealaska.com', 'extremeheatingak.com', 'hardyheating.com',
        'mountainmechanicalak.com', 'klebsheating.com', 'airconditioningprofessionals.com',
        'airsourcealaska.com', 'stinebaugh.com', 'stinebaugh.us', 'wagnerhvac.com',
        'lghvac.com',
        'exxonmobil.com', 'nxsdigital.nl', 'acf.gov', 'aecom.com', 'halliburton.com',
        'target.com', 'sfgov.org', 'dbiweb02.sfgov.org',
        'dot.ca.gov', 'dtsc.ca.gov', 'extension.berkeley.edu', 'gwinnetttech.edu',
        'dogscomfort.pl', 'gdi.com', 'forsythcountytax.com',
        'goodmanmfg.com', 'amana-hac.com', 'fujitsugeneral.com', 'mitsubishipro.com',
        'lg.com', 'hitachi.com', 'panasonic.com', 'gree.com', 'haier.com',
        'berkeley.edu', 'stanford.edu', 'mit.edu', 'harvard.edu',
        'kiewit.com', 'kiewitcareers.kiewit.com', 'gocomfortmaker.com',
        'legacy.gocomfortmaker.com', 'abm.com', 'locations.abm.com',
        'dctechnolabs.com', 'hvac-demo.dctechnolabs.com',
        'hvacanchorage.or.ma', 'homepros.news', 'livingwatersllc.com',
        'or.ma', 'indoortemp.com', 'jadeheatingandair.com',
        # Additional: distributors, suppliers, career sites
        'supplyhouse.com', 'talent.stjude.org', 'costco.com', 'siglers.com',
        'russellsigler.com', 'ferguson.com', 'grainger.com', 'mckinstry.com',
        'rmi.com', 'harriscompanies.com', 'rheem.com', 'noritz.com',
        'aosmith.com', 'bradfordwhite.com', 'rinnai.us', 'takagi.com',
        'navien.com', 'boschthermotechnology.com', 'viesmann.com',
        'viessmann-us.com', 'lennoxstore.com', 'lennoxpros.com',
        'carrierenterprise.com', 'totaline.com', 'johnstone.com',
        'usairconditioning.com', 'goodmanmfg.com', 'amana-hac.com',
        'daikincomfort.com', 'daikinapplied.com', 'bryant.com',
        'payne.com', 'comfortmaker.com', 'daynight.com', 'armstrongair.com',
        'airquest.com', 'ducane.com', 'heiltemp.com', 'keepcool.com',
        'tempstar.com', 'maytag.com', 'whirlpool.com', 'geappliances.com',
        # Additional distributors & manufacturers
        'airtreatment.com', 'bakerdist.com', 'murphynet.com', 'hirsch.com',
        'slakey.com', 'buildzoom.com', 'manta.com', 'york.com',
        'johnsoncontrols.com', 'lghvac.com', 'noritz.com', 'rinnai.us',
        'takagi.com', 'navien.com', 'boschthermotechnology.com',
        'viessmann-us.com', 'lennoxpros.com', 'carrierenterprise.com',
        'totaline.com', 'johnstone.com', 'usairconditioning.com',
        # Authority/directory sites
        'sanfranciscohvacauthority.com', 'alaskahvacauthority.com',
        'hvacsolutionsandservices.com', 'hvacauthority.com',
        # Corporate/manufacturer/SaaS
        'honeywell.com', 'arup.com', 'jacobs.com', 'parker.com', 'tsi.com',
        'tranetechnologies.com', 'trane.com', 'homeserve.com', 'housecallpro.com',
        'servicetitan.com', 'unitedrentals.com', 'goodleap.com', 'thumbtack.com',
        'firstam.com', 'homewarranty.firstam.com', 'chadwellsupply.com',
        'pacesupply.com', 'span.io', 'ncmca.org', 'accoes.com',
        'us-ac.com', 'dmghvac.com',
        # More directories & problematic
        'bbb.org', 'localprobook.com', 'localfind.us', 'powerofjsog.com',
        'promptloop.com', 'awrusa.com', 'wral.com', 'sokolovelaw.com',
        'voomisupply.com', 'nexthvacrepair.com', 'coolingandheatingsanfrancisco.com',
        'calljazz.com', 'hvacsanfrancisco.com', 'schmittheatingsf.net',
        'rkmechanicalairservices.com', 'sanfranciscoairduct.com',
        'sanfranciscoexprethvac.com', 'streetshvac.com',
        # More manufacturers, distributors, directories
        'johnstonesupply.com', 'americanstandardair.com', 'coldaircentral.com',
        'searshomeservices.com', 'tripadvisor.com', 'hvacclasses.org',
        'title24stakeholders.com', 'remotefillsystems.com',
        'goldengatetechnicalhvac.com', 'airbnb.com', 'matrixhginc.com',
        'ies-hvac.com', 'atsair.com', 'southlandind.com',
        'goldengatemechanical.com', 'discovercabrillo.com',
        # More problematic domains
        'researchgate.net', 'csemag.com', 'goldengate.org', 'ebay.com',
        'news4jax.com', 'sothebysrealty.com', 'walmart.com', 'yandex.ru',
        'getyourquote.com', 'yellowpages.com', 'expertise.com', 'bayareaclimatecontrol.com',
        'bearinc.com', 'oldbridgehvac.com', 'primefixclimate.com',
        'kennonhvac.com', 'estesair.com', 'hvacxperts.com',
        'coolseasonhvac.com', 'eliteheatingandairga.com',
        # Major retailers, home services platforms, etc.
        'wafflehouse.com', 'homedepot.com', 'homeyou.com', 'emergencyhvac.org',
        'americancomfortac.com', 'onehourheatandair.com', 'unitedairtemp.com',
        'rsandrews.com', 'foxproshvac.com', 'shumateheatingandair.com',
        'coolray.com', 'greenheatingandcooling.com', 'moncriefair.com',
        'reliance-hvac.com', 'alpharetta-hvac.com', 'metrohci.com',
        'centralheatofga.com', 'callzenair.com', 'coolcarehvacga.com',
        'gagneac.com', 'dynamicairinc.com', 'airconditioningrepaircumming.com',
        'knoxhvac.com', 'americancomfortac.com', 'tri-countyheatingandair.com',
        'holtkamphvac.com', 'cheeksac.com', 'ragsdaleair.com',
        'starserviceshvac.com',
        # More problematic domains found in output
        'chick-fil-a.com', 'lowes.com', 'sunbeltrentals.com', 'forsythpl.org',
        'witn.com', 'nextdoor.com', 'procore.com', 'tumbetin.cam',
        'absoluteservice.com', 'hometown-comfort.com', 'convergint.com',
        'constellation.com', 'casteelair.com', 'absolutehvacservice.com',
        'statonheatingandair.com', 'foxparts.com', 'cummingsheatingair.com',
        'neesehvac.com', 'statonheatingandair.com', 'hansardhvac.com',
        'acetechga.com', 'ableheatingandair.com', 'comfortairflow.com',
        'getcoolatlanta.com', 'justcoolingatl.com', 'coolexpressllcga.com',
        'gacomfort.com', 'conditionedairsystems.com', 'commercialairsystems.net',
        'ibew.org',
        # More problematic from output
        'craigslist.org', 'highergov.com', 'fastenal.com', 'reece.com',
        'northeastern.com', '2jsupply.com', 'jean-grevsmuehl.de',
        'petersheatandcool.com', 'jandbheatingandcooling.com',
        'clementsheatingairllc.com', 'accuratehvac.com',
        'myandersonhvac.com', 'rwheatandair.com', 'birdeye.com',
        'wheree.com', 'jemechanical.com', 'resairhvac.com',
        # Career/corporate pages
        'aerotek.com', 'sodexo.com', 'jobs-ups.com', 'vertiv.com',
        'acehardware.com', 'emcorgroup.com',
        # More from output
        'nationalgeographic.com', 'duke-energy.com', 'tesla.com',
        'hdrinc.com', 'fluor.com', 'lancasterfarming.com',
        'polaris.com', 'sheetmetalinc.com', 'buncha.com', 'tiktok.com',
        'myhighplains.com', 'actionnewsjax.com', 'airconditioningup.com',
        'hvacschool.org', 'denali-industrial.com', 'desertinalaska.com',
        'gensco.com', 'thermalsupplyinc.com', 'alaskanac.com',
        'sbe2010.com', 'msi-ak.com', 'jpsheldon.com', 'coolairalaska.com',
        'abcalaska.org',
    ]
    
    if any(skip in domain for skip in skip_domains):
        return False

    if domain.endswith('.gov') or domain.endswith('.edu') or domain.endswith('.mil'):
        return False

    if any(x in domain for x in ['careers.', 'jobs.', 'demo.', 'legacy.', 'locations.', 'hr.', 'recruiting.']):
        return False

    skip_paths = ['/search', '/search_results', '/find', '/directory', '/companylist',
                  '/company-list', '/contractors', '/contractors/', '/hvac-contractors',
                  '/service-areas', '/service-area', '/dealers', '/find-a-dealer', '/q-', '/jobs',
                  '/careers', '/about-us', '/about/', '/newsroom', '/case-studies', '/project/',
                  '/blog', '/news', '/article', '/press', '/map', '/location',
                  '/catalog', '/explore', '/departments', '/training', '/certification',
                  '/registration', '/platform', '/hiring', '/job', '/career',
                  '/contact', '/contact-us', '/contactus', '/get-a-quote', '/quote',
                  '/request-service', '/schedule', '/booking', '/service-area',
                  '/area-we-serve', '/areas-served', '/service-locations',
                  '/locations/', '/location/', '/branch/', '/branches/',
                  '/commercial/', '/residential/', '/industrial/']

    if any(skip in path for skip in skip_paths):
        return False

    if '#:~:text=' in url:
        return False

    if len(domain) < 4 or domain.count('.') < 1:
        return False

    return True

def get_best_website(row):
    for field in ['extra_url', 'highlighted_link', 'result_url', 'source_domain_url']:
        url = row.get(field, '').strip()
        if is_valid_company_website(url):
            parsed = urlparse(url)
            return f'{parsed.scheme}://{parsed.netloc}'
    return ''

def format_domain_name(domain_or_url: str) -> str:
    """Turn a domain into a readable company title (e.g., masterhvacsolutions.com -> Master HVAC Solutions)."""
    if not domain_or_url:
        return ""
    parsed = urlparse(domain_or_url)
    domain = parsed.netloc if parsed.netloc else domain_or_url
    domain = domain.lower().replace("www.", "")
    base = domain.split(".")[0]
    base = base.replace("-", " ").replace("_", " ")
    # Insert spaces between common HVAC words if concatenated
    replacements = {
        "hvac": " HVAC ",
        "heating": " Heating ",
        "cooling": " Cooling ",
        "air": " Air ",
        "conditioning": " Conditioning ",
        "services": " Services ",
        "service": " Service ",
        "repairs": " Repairs ",
        "repair": " Repair ",
        "solutions": " Solutions ",
        "contractor": " Contractor ",
        "contractors": " Contractors ",
        "mechanical": " Mechanical ",
        "systems": " Systems ",
        "plumbing": " Plumbing ",
        "comfort": " Comfort ",
    }
    for word, repl in replacements.items():
        base = base.replace(word, repl)
    words = [w.capitalize() if w.lower() != "hvac" else "HVAC" for w in base.split() if w.strip()]
    return " ".join(words)


def clean_company_name(name):
    if not name:
        return ''
    name = name.strip()
    # Strip prefixes (including "About Us - ", "Contact - ", etc.)
    name = re.sub(r'^(TOP \d+ BEST |BEST |Contact - |Home - |The Best |ON TIME |Updated \d{4} |Commercial - |Services - |Residential - |About Us - |About - |Contact Us - )', '', name, flags=re.IGNORECASE)
    # Strip trailing ellipses and long descriptions
    name = re.sub(r'\s*\.\.\..*$', '', name)
    # Strip trailing generic HVAC descriptors (e.g., "Fuse Service San Francisco HVAC Air Conditioning" -> "Fuse Service")
    name = re.sub(r'\s+(HVAC|Air Conditioning|Air Conditioner|Heating|Cooling|Plumbing|Sheet Metal|Mechanical|Contractor|Services|Service|Repair|Installation|Commercial|Residential)\s*$', '', name, flags=re.IGNORECASE)
    # Strip trailing filler words (of, the, and, for, in, at, &)
    name = re.sub(r'\s+(of|the|and|for|in|at|&)\s*$', '', name, flags=re.IGNORECASE)
    # Strip corporate suffixes
    name = re.sub(r',?\s*(Inc\.?|LLC|L\.L\.C\.|Corp\.?|Corporation|Company|Co\.?|Ltd\.?|Limited|P\.C\.|P\.L\.C\.|LLP|PLLC)\.?$', '', name, flags=re.IGNORECASE)
    # Strip domain endings if name is a domain
    name = re.sub(r'\.(com|net|org|io|us|biz|info)$', '', name, flags=re.IGNORECASE)
    return name.strip()

def is_generic_or_address(name):
    if not name:
        return True
    name_stripped = name.strip()
    name_lower = name_stripped.lower()
    # Check for domain-like names (even without TLD, e.g., "sanfranciscocahvac", "masterhvacsolutions", "blairhtg")
    # These are typically lowercase strings without spaces that look like domain names
    if re.match(r'^[a-z0-9][a-z0-9\-]*[a-z0-9]$', name_stripped) and len(name_stripped) >= 7:
        # Check if it looks like a concatenated domain name (no spaces, no company suffix)
        if ' ' not in name_stripped and not any(w in name_lower for w in ['inc', 'llc', 'corp', 'company', 'ltd', 'co ', 'co.', 'inc.', 'llc.', 'corp.']):
            # Common domain patterns - concatenated words without spaces
            # If it contains common HVAC terms concatenated, it's likely a domain
            domain_patterns = ['hvac', 'heating', 'cooling', 'aircondition', 'airconditioning', 
                              'mechanical', 'plumbing', 'sheetmetal', 'contractors', 'services',
                              'air', 'heat', 'cool', 'temp', 'comfort', 'climate', 'zone']
            if any(p in name_lower for p in domain_patterns):
                return True
            # Also catch common company name patterns that are likely domains (short concatenated words)
            # e.g., blairhtg, morrisvac, calibermech, etc.
            if len(name_stripped) <= 15:
                return True
    # Generic HVAC terms
    generic_terms = ['hvac', 'heating', 'cooling', 'air conditioning', 'air condition',
                     'plumbing', 'contractor', 'service', 'repair', 'installation',
                     'commercial', 'residential', 'hvac/r', 'hvac services',
                     'hvac contractor', 'hvac company',
                     'hvac contractors', 'hvac repair', 'hvac installation',
                     'air conditioning repair', 'air conditioning service',
                     'heating repair', 'heating service', 'cooling repair', 'cooling service']
    if name_lower in generic_terms:
        return True
    # Single generic words that aren't company names
    single_generic = ['home', 'about', 'contact', 'services', 'service', 'products',
                      'solutions', 'company', 'business', 'corporation', 'inc',
                      'llc', 'corp', 'ltd', 'co', 'store', 'shop', 'online',
                      'welcome', 'index', 'main', 'default', 'page', 'site',
                      'web', 'website', 'blog', 'news', 'careers', 'jobs',
                      'login', 'register', 'account', 'dashboard', 'portal',
                      'search', 'find', 'directory', 'list', 'listing',
                      'map', 'location', 'locations', 'branch', 'branches',
                      'dealer', 'dealers', 'distributor', 'distributors',
                      'supplier', 'suppliers', 'wholesale', 'retail', 'about us',
                      'contact us', 'our services', 'our team', 'our company',
                      'our story', 'careers at', 'jobs at', 'work at', 'join us',
                      'hiring', 'employment', 'career', 'sodexo', 'ups', 'aerotek',
                      'vertiv', 'ace hardware', 'emcor']
    if name_lower in single_generic:
        return True
    # Multi-word generic phrases
    generic_phrases = ['about us', 'contact us', 'our services', 'our team', 'our company',
                       'our story', 'careers at', 'jobs at', 'work at', 'join us', 'hiring now',
                       'we are hiring', 'career opportunities', 'job openings', 'apply now',
                       'family-owned hvac contractor', 'family owned hvac', 'locally owned',
                       'licensed and insured', 'free estimates', '24/7 service', 'emergency service',
                       'ac hvac services', 'us heating and air conditioning', 'dayton hvac contractor',
                       'ohio hvac', 'central air', 'heating and air conditioning',
                       'heating and air conditioner', 'heating cooling',
                       'heating ac services', 'hvac company in',
                       'commercial hvac equipment', 'commercial hvac', 'residential hvac',
                       'hvac services san francisco', 'hvac san francisco',
                       'fuse service san francisco', 'san francisco hvac',
                       'hvac georgetown oh', 'georgetown oh hvac',
                       'heating cooling solutions', 'hvac archives',
                       'residential hvac anchorage', 'commercial hvac anchorage']
    if name_lower in generic_phrases:
        return True
    # Check if name is composed mostly of generic HVAC words (e.g., "Commercial HVAC equipment", "Heating & AC Services")
    # Only apply to longer names (5+ words) to avoid catching real company names
    generic_words = ['hvac', 'heating', 'cooling', 'air', 'conditioning', 'conditioner',
                     'plumbing', 'contractor', 'service', 'services', 'repair', 'installation',
                     'commercial', 'residential', 'mechanical', 'equipment', 'solutions',
                     'company', 'inc', 'llc', 'corp', 'ltd', 'co', 'and', 'the', 'of', 'in',
                     'for', 'with', 'your', 'our', 'san', 'francisco', 'ohio', 'georgetown',
                     'anchorage', 'dayton', 'central', 'fuse', 'ac']
    words = name_lower.split()
    if len(words) >= 5:
        generic_count = sum(1 for w in words if w in generic_words)
        if generic_count / len(words) >= 0.8:  # 80% or more generic words
            return True
    address_indicators = ['st ', 'street', 'ave ', 'avenue', 'blvd', 'road', 'rd ', 'dr ',
                          'unit', 'suite', 'ste ', 'ca 9', 'ca 94', 'ca 95', 'ca 96',
                          '#', 'floor', 'fl ', 'building', 'bldg']
    if any(ind in name_lower for ind in address_indicators):
        return True
    # Reject short abbreviations like "S.F.", "N.Y.", etc. (2-4 chars with dots)
    if re.match(r'^[A-Z]\.([A-Z]\.?)+$', name_stripped) and len(name_stripped) <= 5:
        return True
    # Reject very short names (likely abbreviations or noise)
    if len(name_stripped) <= 3:
        return True
    return False

def is_description(name):
    """Check if name looks like a description rather than a company name"""
    if not name:
        return True
    name_lower = name.lower()
    # Phrases that indicate this is a description
    desc_phrases = [
        'services in', 'service in', 'installation', 'repair', 'specializes',
        'offers', 'provides', 'source for', 'types of', 'found in',
        'distributors', 'distributor', 'dealer', 'dealer in',
        'expert', 'experts', 'professional', 'top rated', 'best ',
        'contact', 'call', 'free estimates', 'prompt services',
        'affordable rates', 'quality workmanship', 'serving',
        'since 19', 'since 20', 'family owned', 'locally owned',
        'licensed', 'insured', 'bonded', 'certified', 'diamond certified',
        'trusted', 'reliable', 'affordable', 'emergency',
        '24/7', '24 hour', 'same day', 'fast ', 'quick ',
    ]
    if any(phrase in name_lower for phrase in desc_phrases):
        return True
    # If it contains common sentence words
    sentence_words = [' and ', ' the ', ' for ', ' with ', ' your ', ' our ', ' my ', ' at ', ' in ', ' of ', ' to ', ' from ']
    # But only if it's a longer phrase (likely a sentence) - use higher threshold
    # Count how many sentence words appear
    sentence_count = sum(1 for w in sentence_words if w in name_lower)
    if len(name) > 40 and sentence_count >= 2:
        return True
    return False

def extract_company_from_domain(url):
    """Extract potential company name from domain"""
    if not url:
        return ''
    parsed = urlparse(url)
    domain = parsed.netloc.lower().replace('www.', '')
    # Remove TLD
    parts = domain.split('.')
    if len(parts) >= 2:
        # Get the main domain part
        main = parts[-2]  # e.g., 'sanfranciscocahvac' from 'sanfranciscocahvac.com'
        # Clean it up - split camelCase or dashes
        main = main.replace('-', ' ').replace('_', ' ')
        # Split camelCase (e.g., 'sanfranciscocahvac' -> 'san francisco ca hvac')
        # Add space before uppercase letters followed by lowercase
        import re
        main = re.sub(r'([a-z])([A-Z])', r'\1 \2', main)
        # Also try to split known concatenated words (common HVAC terms)
        # This is a heuristic - split on common word boundaries using regex with word boundaries
        known_splits = ['hvac', 'heating', 'cooling', 'air', 'conditioning', 'conditioner',
                        'mechanical', 'plumbing', 'service', 'services', 'repair', 'install',
                        'comfort', 'climate', 'temp', 'zone', 'master', 'pro',
                        'san', 'francisco', 'ca', 'ohio', 'oh', 'akron',
                        'georgetown', 'mt', 'orab', 'dayton', 'cincinnati', 'cleveland',
                        'columbus', 'toledo', 'youngstown', 'canton', 'mansfield',
                        'anchorage', 'alaska', 'ak', 'arctic', 'stevens', 'even',
                        'asm', 'assembly', 'rts', 'rt', 'kens', 'ken', 'blair', 'htg',
                        'galaxy', 'fuse', 'repairs', 'sf', 'associated',
                        'schmitt', 'calvey', 'peterson', 'robinson', 'thomas', 'galbraith',
                        'rnsmith', 'patriot', 'moore', 'henry', 'hill', 'cowboys',
                        'caliber', 'comfort', 'airtron', 'anytime', 'abco', 'city',
                        'bryant', 'keith', 'twin', 'tap', 'bush', 'rouse', 'right',
                        'middletown', 'lebanon', 'care', 'southern', 'central',
                        'choice', 'bridgetown', 'wright', 'morrish', 'morris',
                        'heatingandair', 'heatingcooling', 'hvacrepair', 'hvacsales',
                        'and']
        # Try to split on known words (longest first to avoid partial matches)
        known_splits.sort(key=len, reverse=True)
        for word in known_splits:
            if word in main and main != word:
                # Split on word boundaries using regex to avoid partial matches like "even" in "stevens"
                main = re.sub(r'(?<=[a-z])' + re.escape(word) + r'(?=[a-z])', f' {word} ', main)
                main = re.sub(r'^' + re.escape(word) + r'(?=[a-z])', f'{word} ', main)
                main = re.sub(r'(?<=[a-z])' + re.escape(word) + r'$', f' {word}', main)
        # Clean up multiple spaces
        main = re.sub(r'\s+', ' ', main).strip()
        # Title case
        words = main.split()
        # Known acronyms that should be uppercase
        acronyms = {'hvac', 'asm', 'rt', 'rts', 'ac', 'ca', 'oh', 'ak', 'mt', 'sf', 'htg', 'afp', 'kens', 'rnsmith'}
        cleaned = ' '.join(w.upper() if w.lower() in acronyms else w.capitalize() for w in words if len(w) > 2)
        if cleaned and len(cleaned) > 3:
            return cleaned
    return ''

def extract_name_from_title(title):
    """Extract company name from title field which often has format 'Company Name | Description' or 'Company Name: Description' or 'Page Title - Company Name'"""
    if not title:
        return ''
    # First try to split by | or : or em dash or en dash and take the first part
    for sep in [' | ', ' - ', ': ', ' — ', ' – ']:
        if sep in title:
            parts = title.split(sep)
            # Try first part
            first_part = parts[0].strip()
            cleaned = clean_company_name(first_part)
            if cleaned and not is_generic_or_address(cleaned) and not is_description(cleaned):
                return cleaned
            # If first part is generic (like "Home", "Contact Us", "Commercial"), try second part
            if len(parts) > 1:
                second_part = parts[1].strip()
                cleaned = clean_company_name(second_part)
                if cleaned and not is_generic_or_address(cleaned) and not is_description(cleaned):
                    return cleaned
    # If no separator, clean the whole title
    cleaned = clean_company_name(title)
    if cleaned and not is_generic_or_address(cleaned) and not is_description(cleaned):
        return cleaned
    return ''

def is_bad_name(name):
    """Check if name is a phone number, address, or other non-company name"""
    if not name:
        return True
    name_stripped = name.strip()
    # Phone number patterns
    phone_patterns = [
        r'^\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{4}$',  # (510) 518-8965 or 510-518-8965
        r'^\d{10}$',  # 5105188965
        r'^\d{3}[-.]\d{3}[-.]\d{4}$',  # 937-690-6060 or 937.690.6060
    ]
    for pattern in phone_patterns:
        if re.match(pattern, name_stripped):
            return True
    # Domain-like names (e.g., schmittheating.com, sanfranciscoheatingandairconditioning.com)
    if re.match(r'^[a-zA-Z0-9][a-zA-Z0-9\-\.]*\.[a-z]{2,}$', name_stripped):
        # Check if it looks like a domain (contains a dot and TLD)
        if '.' in name_stripped and not any(w in name_stripped.lower() for w in ['inc', 'llc', 'corp', 'company']):
            return True
    # Address-like (starts with number and has street indicators)
    if re.match(r'^\d+\s+\w+', name_stripped):
        address_indicators = ['st', 'street', 'ave', 'avenue', 'blvd', 'road', 'rd', 'dr',
                              'unit', 'suite', 'ste', 'floor', 'fl', 'building', 'bldg',
                              'ca 9', '#']
        name_lower = name_stripped.lower()
        if any(ind in name_lower for ind in address_indicators):
            return True
    # City, State pattern like "South San Francisco CA" or "San Francisco"
    city_state_pattern = r'^[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*,\s*[A-Z]{2}$'
    if re.match(city_state_pattern, name_stripped):
        return True
    # Just city name (if it's a known city, but hard to detect - check for common patterns)
    if re.match(r'^[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*$', name_stripped):
        # Could be a city name - if it's short and no other company indicators, skip
        if len(name_stripped.split()) <= 3 and not any(w in name_stripped.lower() for w in ['heating', 'air', 'cooling', 'hvac', 'mechanical', 'service', 'repair', 'inc', 'llc', 'corp', 'company', 'contractors', 'systems', 'plumbing', 'sheetmetal', 'aircraft', 'construction', 'engineering']):
            return True
    # City State pattern without comma (e.g., "Mt Orab Ohio", "South San Francisco CA")
    city_state_no_comma = r'^[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+[A-Z]{2}$'
    if re.match(city_state_no_comma, name_stripped):
        return True
    return False

def get_company_name(row):
    # First, try source_name - often has the cleanest company names
    source = row.get('source_name', '').strip()
    if source:
        cleaned = clean_company_name(source)
        if cleaned and not is_generic_or_address(cleaned) and not is_description(cleaned):
            return cleaned
        # If source is a domain, try to extract company name from it
        if '.' in source and not is_bad_name(source):
            domain_name = extract_company_from_domain(source)
            if domain_name and not is_generic_or_address(domain_name) and not is_description(domain_name):
                return domain_name

    # Second, try business_name_or_detail - but skip if it's a phone number, address, or generic
    name = row.get('business_name_or_detail', '').strip()
    if name and not is_bad_name(name):
        cleaned = clean_company_name(name)
        if cleaned and not is_generic_or_address(cleaned) and not is_description(cleaned):
            return cleaned

    # Third, try title field - often has format "Company Name | Description" or "Page Title - Company Name"
    title = row.get('title', '').strip()
    if title:
        extracted = extract_name_from_title(title)
        if extracted:
            return extracted

    # Fallback: try to extract from website domain
    website = get_best_website(row)
    if website:
        domain_name = extract_company_from_domain(website)
        if domain_name and not is_generic_or_address(domain_name) and not is_description(domain_name):
            return domain_name

    return ''

with open(input_file, 'r', encoding='utf-8-sig') as infile:
    reader = csv.DictReader(infile)
    fieldnames = ['email', 'first_name', 'last_name', 'company', 'phone', 'website']

    rows = []
    for row in reader:
        new_row = {fn: '' for fn in fieldnames}
        new_row['company'] = get_company_name(row)
        new_row['email'] = row.get('extracted_email', '').strip()
        new_row['phone'] = extract_phone(row.get('snippet', ''))
        new_row['website'] = get_best_website(row)
        rows.append(new_row)

filtered_rows = [r for r in rows if r['company'] and r['website']]

# Deduplicate by website (keeping the row with the most information)
deduped: dict[str, dict] = {}
for r in filtered_rows:
    web_key = r['website'].lower().rstrip('/')
    if web_key not in deduped:
        deduped[web_key] = r
    else:
        # Prefer the one with email or phone or longer company name
        existing = deduped[web_key]
        score_existing = (1 if existing.get('email') else 0) + (1 if existing.get('phone') else 0) + len(existing.get('company', ''))
        score_new = (1 if r.get('email') else 0) + (1 if r.get('phone') else 0) + len(r.get('company', ''))
        if score_new > score_existing:
            deduped[web_key] = r

final_rows = list(deduped.values())

with open(output_file, 'w', newline='', encoding='utf-8') as outfile:
    writer = csv.DictWriter(outfile, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(final_rows)

print(f'Total rows: {len(rows)}')
print(f'Filtered rows (with company + valid website): {len(filtered_rows)}')
print(f'Unique deduplicated leads: {len(final_rows)}')
print('Sample:', final_rows[0] if final_rows else 'empty')

websites = set(r['website'] for r in final_rows)
print(f'\nUnique websites ({len(websites)}):')
for w in sorted(websites)[:30]:
    print(f'  {w}')