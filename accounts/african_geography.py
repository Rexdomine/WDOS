"""
Authoritative first-level administrative geography for all 55 African countries.
Complies with African Union member states and ISO 3166-1 / 3166-2 conventions.
Provides stable IDs, display names, country-appropriate administrative labels,
and dependent regional/district definitions.
"""

AFRICAN_COUNTRIES = {
    "Algeria": {
        "code": "DZ",
        "name": "Algeria",
        "admin_label": "Province / Wilaya",
        "local_label": "District / Daïra",
        "regions": [
            ("DZ-01", "Adrar"), ("DZ-16", "Algiers"), ("DZ-44", "Aïn Defla"),
            ("DZ-46", "Aïn Témouchent"), ("DZ-23", "Annaba"), ("DZ-05", "Batna"),
            ("DZ-07", "Biskra"), ("DZ-09", "Blida"), ("DZ-34", "Bordj Bou Arréridj"),
            ("DZ-50", "Bordj Badji Mokhtar"), ("DZ-10", "Bouira"), ("DZ-35", "Boumerdès"),
            ("DZ-08", "Béchar"), ("DZ-52", "Béni Abbès"), ("DZ-06", "Béjaïa"),
            ("DZ-02", "Chlef"), ("DZ-25", "Constantine"), ("DZ-56", "Djanet"),
            ("DZ-17", "Djelfa"), ("DZ-32", "El Bayadh"), ("DZ-57", "El M'Ghair"),
            ("DZ-58", "El Meniaa"), ("DZ-39", "El Oued"), ("DZ-36", "El Tarf"),
            ("DZ-47", "Ghardaïa"), ("DZ-24", "Guelma"), ("DZ-33", "Illizi"),
            ("DZ-54", "In Guezzam"), ("DZ-53", "In Salah"), ("DZ-18", "Jijel"),
            ("DZ-40", "Khenchela"), ("DZ-03", "Laghouat"), ("DZ-28", "M'Sila"),
            ("DZ-29", "Mascara"), ("DZ-43", "Mila"), ("DZ-27", "Mostaganem"),
            ("DZ-26", "Médéa"), ("DZ-45", "Naâma"), ("DZ-31", "Oran"),
            ("DZ-51", "Ouled Djellal"), ("DZ-30", "Ouargla"), ("DZ-04", "Oum El Bouaghi"),
            ("DZ-48", "Relizane"), ("DZ-20", "Saïda"), ("DZ-22", "Sidi Bel Abbès"),
            ("DZ-21", "Skikda"), ("DZ-41", "Souk Ahras"), ("DZ-19", "Sétif"),
            ("DZ-11", "Tamanrasset"), ("DZ-14", "Tiaret"), ("DZ-49", "Timimoun"),
            ("DZ-37", "Tindouf"), ("DZ-42", "Tipaza"), ("DZ-38", "Tissemsilt"),
            ("DZ-15", "Tizi Ouzou"), ("DZ-13", "Tlemcen"), ("DZ-55", "Touggourt"),
            ("DZ-12", "Tébessa"),
        ],
    },
    "Angola": {
        "code": "AO",
        "name": "Angola",
        "admin_label": "Province",
        "local_label": "Municipality",
        "regions": [
            ("AO-BGO", "Bengo"), ("AO-BGU", "Benguela"), ("AO-BIE", "Bié"),
            ("AO-CAB", "Cabinda"), ("AO-CCU", "Cuando Cubango"), ("AO-CNO", "Cuanza Norte"),
            ("AO-CUS", "Cuanza Sul"), ("AO-CNN", "Cunene"), ("AO-HUA", "Huambo"),
            ("AO-HUI", "Huíla"), ("AO-LUA", "Luanda"), ("AO-LNO", "Lunda Norte"),
            ("AO-LSU", "Lunda Sul"), ("AO-MAL", "Malanje"), ("AO-MOX", "Moxico"),
            ("AO-NAM", "Namibe"), ("AO-UIG", "Uíge"), ("AO-ZAI", "Zaire"),
        ],
    },
    "Benin": {
        "code": "BJ",
        "name": "Benin",
        "admin_label": "Department",
        "local_label": "Commune",
        "regions": [
            ("BJ-AL", "Alibori"), ("BJ-AK", "Atakora"), ("BJ-AQ", "Atlantique"),
            ("BJ-BO", "Borgou"), ("BJ-CO", "Collines"), ("BJ-KO", "Couffo"),
            ("BJ-DO", "Donga"), ("BJ-LI", "Littoral"), ("BJ-MO", "Mono"),
            ("BJ-OU", "Ouémé"), ("BJ-PL", "Plateau"), ("BJ-ZO", "Zou"),
        ],
    },
    "Botswana": {
        "code": "BW",
        "name": "Botswana",
        "admin_label": "District",
        "local_label": "Sub-district",
        "regions": [
            ("BW-CE", "Central"), ("BW-CH", "Chobe"), ("BW-FR", "Francistown"),
            ("BW-GA", "Gaborone"), ("BW-GH", "Ghanzi"), ("BW-JW", "Jwaneng"),
            ("BW-KG", "Kgalagadi"), ("BW-KL", "Kgatleng"), ("BW-KW", "Kweneng"),
            ("BW-LO", "Lobatse"), ("BW-NG", "Ngamiland"), ("BW-NE", "North-East"),
            ("BW-OR", "Orapa"), ("BW-SP", "Selebi-Phikwe"), ("BW-SE", "South-East"),
            ("BW-SO", "Southern"), ("BW-SW", "Sowa"),
        ],
    },
    "Burkina Faso": {
        "code": "BF",
        "name": "Burkina Faso",
        "admin_label": "Region",
        "local_label": "Province",
        "regions": [
            ("BF-01", "Boucle du Mouhoun"), ("BF-02", "Cascades"), ("BF-03", "Centre"),
            ("BF-04", "Centre-Est"), ("BF-05", "Centre-Nord"), ("BF-06", "Centre-Ouest"),
            ("BF-07", "Centre-Sud"), ("BF-08", "Est"), ("BF-09", "Hauts-Bassins"),
            ("BF-10", "Nord"), ("BF-11", "Plateau-Central"), ("BF-12", "Sahel"),
            ("BF-13", "Sud-Ouest"),
        ],
    },
    "Burundi": {
        "code": "BI",
        "name": "Burundi",
        "admin_label": "Province",
        "local_label": "Commune",
        "regions": [
            ("BI-BB", "Bubanza"), ("BI-BM", "Bujumbura Mairie"), ("BI-BL", "Bujumbura Rural"),
            ("BI-BR", "Bururi"), ("BI-CA", "Cankuzo"), ("BI-CI", "Cibitoke"),
            ("BI-GI", "Gitega"), ("BI-KR", "Karuzi"), ("BI-KY", "Kayanza"),
            ("BI-KI", "Kirundo"), ("BI-MA", "Makamba"), ("BI-MU", "Muramvya"),
            ("BI-MY", "Muyinga"), ("BI-MW", "Mwaro"), ("BI-NG", "Ngozi"),
            ("BI-RM", "Rumonge"), ("BI-RT", "Rutana"), ("BI-RY", "Ruyigi"),
        ],
    },
    "Cabo Verde": {
        "code": "CV",
        "name": "Cabo Verde",
        "admin_label": "Municipality",
        "local_label": "Parish",
        "regions": [
            ("CV-BV", "Boa Vista"), ("CV-BR", "Brava"), ("CV-MA", "Maio"),
            ("CV-MO", "Mosteiros"), ("CV-PA", "Paul"), ("CV-PN", "Porto Novo"),
            ("CV-PR", "Praia"), ("CV-RB", "Ribeira Brava"), ("CV-RG", "Ribeira Grande"),
            ("CV-RS", "Ribeira Grande de Santiago"), ("CV-SL", "Sal"),
            ("CV-CA", "Santa Catarina"), ("CV-CF", "Santa Catarina do Fogo"),
            ("CV-CR", "Santa Cruz"), ("CV-SD", "São Domingos"), ("CV-SF", "São Filipe"),
            ("CV-SO", "São Lourenço dos Órgãos"), ("CV-SM", "São Miguel"),
            ("CV-SS", "São Salvador do Mundo"), ("CV-SV", "São Vicente"),
            ("CV-TA", "Tarrafal"), ("CV-TS", "Tarrafal de São Nicolau"),
        ],
    },
    "Cameroon": {
        "code": "CM",
        "name": "Cameroon",
        "admin_label": "Region",
        "local_label": "Department",
        "regions": [
            ("CM-AD", "Adamaoua"), ("CM-CE", "Centre"), ("CM-ES", "East"),
            ("CM-EN", "Far North"), ("CM-LT", "Littoral"), ("CM-NO", "North"),
            ("CM-NW", "North-West"), ("CM-SU", "South"), ("CM-SW", "South-West"),
            ("CM-OU", "West"),
        ],
    },
    "Central African Republic": {
        "code": "CF",
        "name": "Central African Republic",
        "admin_label": "Prefecture",
        "local_label": "Sub-prefecture",
        "regions": [
            ("CF-BB", "Bamingui-Bangoran"), ("CF-BGF", "Bangui"), ("CF-BK", "Basse-Kotto"),
            ("CF-HK", "Haute-Kotto"), ("CF-HM", "Haut-Mbomou"), ("CF-KG", "Kémo"),
            ("CF-LB", "Lobaye"), ("CF-MB", "Mambéré"), ("CF-MK", "Mambéré-Kadéï"),
            ("CF-MBM", "Mbomou"), ("CF-NG", "Nana-Gébizi"), ("CF-NM", "Nana-Mambéré"),
            ("CF-OP", "Ombella-M'Poko"), ("CF-UK", "Ouaka"), ("CF-AC", "Ouham"),
            ("CF-OF", "Ouham-Fafa"), ("CF-OPD", "Ouham-Pendé"), ("CF-SE", "Sangha-Mbaéré"),
            ("CF-VK", "Vakaga"),
        ],
    },
    "Chad": {
        "code": "TD",
        "name": "Chad",
        "admin_label": "Province",
        "local_label": "Department",
        "regions": [
            ("TD-BG", "Bahr el Gazel"), ("TD-BA", "Batha"), ("TD-BO", "Borkou"),
            ("TD-CB", "Chari-Baguirmi"), ("TD-EE", "Ennedi-Est"), ("TD-EO", "Ennedi-Ouest"),
            ("TD-GR", "Guéra"), ("TD-HL", "Hadjer-Lamis"), ("TD-KA", "Kanem"),
            ("TD-LC", "Lac"), ("TD-LO", "Logone Occidental"), ("TD-LR", "Logone Oriental"),
            ("TD-MA", "Mandoul"), ("TD-ME", "Mayo-Kebbi Est"), ("TD-MO", "Mayo-Kebbi Ouest"),
            ("TD-MC", "Moyen-Chari"), ("TD-ND", "N'Djamena"), ("TD-OD", "Ouaddaï"),
            ("TD-SA", "Salamat"), ("TD-SI", "Sila"), ("TD-TA", "Tandjilé"),
            ("TD-TI", "Tibesti"), ("TD-WF", "Wadi Fira"),
        ],
    },
    "Comoros": {
        "code": "KM",
        "name": "Comoros",
        "admin_label": "Island",
        "local_label": "Prefecture",
        "regions": [
            ("KM-A", "Anjouan"), ("KM-G", "Grande Comore"), ("KM-M", "Mohéli"),
        ],
    },
    "Congo (Republic of the)": {
        "code": "CG",
        "name": "Congo (Republic of the)",
        "admin_label": "Department",
        "local_label": "District",
        "regions": [
            ("CG-11", "Bouenza"), ("CG-BZV", "Brazzaville"), ("CG-8", "Cuvette"),
            ("CG-15", "Cuvette-Ouest"), ("CG-5", "Kouilou"), ("CG-2", "Lékoumou"),
            ("CG-7", "Likouala"), ("CG-9", "Niari"), ("CG-14", "Plateaux"),
            ("CG-16", "Pointe-Noire"), ("CG-12", "Pool"), ("CG-13", "Sangha"),
        ],
    },
    "Congo (Democratic Republic of the)": {
        "code": "CD",
        "name": "Congo (Democratic Republic of the)",
        "admin_label": "Province",
        "local_label": "Territory",
        "regions": [
            ("CD-BU", "Bas-Uélé"), ("CD-EQ", "Équateur"), ("CD-HK", "Haut-Katanga"),
            ("CD-HL", "Haut-Lomami"), ("CD-HU", "Haut-Uélé"), ("CD-IT", "Ituri"),
            ("CD-KS", "Kasaï"), ("CD-KC", "Kasaï-Central"), ("CD-KO", "Kasaï-Oriental"),
            ("CD-KN", "Kinshasa"), ("CD-BC", "Kongo Central"), ("CD-KG", "Kwango"),
            ("CD-KL", "Kwilu"), ("CD-LO", "Lomami"), ("CD-LU", "Lualaba"),
            ("CD-MN", "Mai-Ndombe"), ("CD-MA", "Maniema"), ("CD-MO", "Mongala"),
            ("CD-NK", "Nord-Kivu"), ("CD-NU", "Nord-Ubangi"), ("CD-SA", "Sankuru"),
            ("CD-SK", "Sud-Kivu"), ("CD-SU", "Sud-Ubangi"), ("CD-TA", "Tanganyika"),
            ("CD-TO", "Tshopo"), ("CD-TU", "Tshuapa"),
        ],
    },
    "Côte d'Ivoire": {
        "code": "CI",
        "name": "Côte d'Ivoire",
        "admin_label": "District",
        "local_label": "Region",
        "regions": [
            ("CI-AB", "Abidjan"), ("CI-BS", "Bas-Sassandra"), ("CI-CM", "Comoé"),
            ("CI-DN", "Denguélé"), ("CI-GD", "Gôh-Djiboua"), ("CI-LC", "Lacs"),
            ("CI-LG", "Lagunes"), ("CI-MG", "Montagnes"), ("CI-SM", "Sassandra-Marahoué"),
            ("CI-SV", "Savanes"), ("CI-VB", "Vallée du Bandama"), ("CI-WR", "Woroba"),
            ("CI-YM", "Yamoussoukro"), ("CI-ZZ", "Zanzan"),
        ],
    },
    "Djibouti": {
        "code": "DJ",
        "name": "Djibouti",
        "admin_label": "Region",
        "local_label": "District",
        "regions": [
            ("DJ-AS", "Ali Sabieh"), ("DJ-AR", "Arta"), ("DJ-DI", "Dikhil"),
            ("DJ-DJ", "Djibouti"), ("DJ-OB", "Obock"), ("DJ-TA", "Tadjourah"),
        ],
    },
    "Egypt": {
        "code": "EG",
        "name": "Egypt",
        "admin_label": "Governorate",
        "local_label": "Markaz / District",
        "regions": [
            ("EG-ALX", "Alexandria"), ("EG-ASN", "Aswan"), ("EG-AST", "Asyut"),
            ("EG-BA", "Red Sea"), ("EG-BH", "Beheira"), ("EG-BNS", "Beni Suef"),
            ("EG-C", "Cairo"), ("EG-DK", "Dakahlia"), ("EG-DT", "Damietta"),
            ("EG-FYM", "Faiyum"), ("EG-GH", "Gharbia"), ("EG-GZ", "Giza"),
            ("EG-IS", "Ismailia"), ("EG-JS", "South Sinai"), ("EG-KB", "Qalyubia"),
            ("EG-KFS", "Kafr El Sheikh"), ("EG-KN", "Qena"), ("EG-LX", "Luxor"),
            ("EG-MN", "Minya"), ("EG-MNF", "Monufia"), ("EG-MT", "Matrouh"),
            ("EG-PTS", "Port Said"), ("EG-SHG", "Sohag"), ("EG-SHR", "Sharqia"),
            ("EG-SIN", "North Sinai"), ("EG-SUZ", "Suez"), ("EG-WAD", "New Valley"),
        ],
    },
    "Equatorial Guinea": {
        "code": "GQ",
        "name": "Equatorial Guinea",
        "admin_label": "Province",
        "local_label": "District",
        "regions": [
            ("GQ-AN", "Annobón"), ("GQ-BN", "Bioko Norte"), ("GQ-BS", "Bioko Sur"),
            ("GQ-CS", "Centro Sur"), ("GQ-DJ", "Djibloho"), ("GQ-KN", "Kié-Ntem"),
            ("GQ-LI", "Litoral"), ("GQ-WN", "Wele-Nzas"),
        ],
    },
    "Eritrea": {
        "code": "ER",
        "name": "Eritrea",
        "admin_label": "Region",
        "local_label": "Sub-region",
        "regions": [
            ("ER-AN", "Anseba"), ("ER-DU", "Debub"), ("ER-GB", "Gash-Barka"),
            ("ER-MA", "Maekel"), ("ER-SK", "Northern Red Sea"), ("ER-DK", "Southern Red Sea"),
        ],
    },
    "Eswatini": {
        "code": "SZ",
        "name": "Eswatini",
        "admin_label": "Region",
        "local_label": "Tinkhundla",
        "regions": [
            ("SZ-HH", "Hhohho"), ("SZ-LU", "Lubombo"), ("SZ-MA", "Manzini"),
            ("SZ-SH", "Shiselweni"),
        ],
    },
    "Ethiopia": {
        "code": "ET",
        "name": "Ethiopia",
        "admin_label": "Region",
        "local_label": "Zone",
        "regions": [
            ("ET-AA", "Addis Ababa"), ("ET-AF", "Afar"), ("ET-AM", "Amhara"),
            ("ET-BE", "Benishangul-Gumuz"), ("ET-CE", "Central Ethiopia"),
            ("ET-DD", "Dire Dawa"), ("ET-GA", "Gambela"), ("ET-HA", "Harari"),
            ("ET-OR", "Oromia"), ("ET-SI", "Sidama"), ("ET-SO", "Somali"),
            ("ET-SE", "South Ethiopia"), ("ET-SW", "South West Ethiopia Peoples'"),
            ("ET-TI", "Tigray"),
        ],
    },
    "Gabon": {
        "code": "GA",
        "name": "Gabon",
        "admin_label": "Province",
        "local_label": "Department",
        "regions": [
            ("GA-1", "Estuaire"), ("GA-2", "Haut-Ogooué"), ("GA-3", "Moyen-Ogooué"),
            ("GA-4", "Ngounié"), ("GA-5", "Nyanga"), ("GA-6", "Ogooué-Ivindo"),
            ("GA-7", "Ogooué-Lolo"), ("GA-8", "Ogooué-Maritime"), ("GA-9", "Woleu-Ntem"),
        ],
    },
    "Gambia": {
        "code": "GM",
        "name": "Gambia",
        "admin_label": "Region",
        "local_label": "District",
        "regions": [
            ("GM-B", "Banjul"), ("GM-M", "Central River"), ("GM-L", "Lower River"),
            ("GM-N", "North Bank"), ("GM-U", "Upper River"), ("GM-W", "West Coast"),
        ],
    },
    "Ghana": {
        "code": "GH",
        "name": "Ghana",
        "admin_label": "Region",
        "local_label": "District",
        "regions": [
            ("GH-AH", "Ahafo"), ("GH-AF", "Ashanti"), ("GH-BO", "Bono"),
            ("GH-BE", "Bono East"), ("GH-CP", "Central"), ("GH-EP", "Eastern"),
            ("GH-AA", "Greater Accra"), ("GH-NE", "North East"), ("GH-NP", "Northern"),
            ("GH-OT", "Oti"), ("GH-SV", "Savannah"), ("GH-UE", "Upper East"),
            ("GH-UW", "Upper West"), ("GH-TV", "Volta"), ("GH-WP", "Western"),
            ("GH-WN", "Western North"),
        ],
    },
    "Guinea": {
        "code": "GN",
        "name": "Guinea",
        "admin_label": "Region",
        "local_label": "Prefecture",
        "regions": [
            ("GN-B", "Boké"), ("GN-C", "Conakry"), ("GN-F", "Faranah"),
            ("GN-K", "Kankan"), ("GN-D", "Kindia"), ("GN-L", "Labé"),
            ("GN-M", "Mamou"), ("GN-N", "Nzérékoré"),
        ],
    },
    "Guinea-Bissau": {
        "code": "GW",
        "name": "Guinea-Bissau",
        "admin_label": "Region",
        "local_label": "Sector",
        "regions": [
            ("GW-BA", "Bafatá"), ("GW-BM", "Biombo"), ("GW-BS", "Bissau"),
            ("GW-BL", "Bolama"), ("GW-CA", "Cacheu"), ("GW-GA", "Gabú"),
            ("GW-OI", "Oio"), ("GW-QU", "Quinara"), ("GW-TO", "Tombali"),
        ],
    },
    "Kenya": {
        "code": "KE",
        "name": "Kenya",
        "admin_label": "County",
        "local_label": "Sub-county",
        "regions": [
            ("KE-01", "Baringo"), ("KE-02", "Bomet"), ("KE-03", "Bungoma"),
            ("KE-04", "Busia"), ("KE-05", "Elgeyo-Marakwet"), ("KE-06", "Embu"),
            ("KE-07", "Garissa"), ("KE-08", "Homa Bay"), ("KE-09", "Isiolo"),
            ("KE-10", "Kajiado"), ("KE-11", "Kakamega"), ("KE-12", "Kericho"),
            ("KE-13", "Kiambu"), ("KE-14", "Kilifi"), ("KE-15", "Kirinyaga"),
            ("KE-16", "Kisii"), ("KE-17", "Kisumu"), ("KE-18", "Kitui"),
            ("KE-19", "Kwale"), ("KE-20", "Laikipia"), ("KE-21", "Lamu"),
            ("KE-22", "Machakos"), ("KE-23", "Makueni"), ("KE-24", "Mandera"),
            ("KE-25", "Marsabit"), ("KE-26", "Meru"), ("KE-27", "Migori"),
            ("KE-28", "Mombasa"), ("KE-29", "Murang'a"), ("KE-30", "Nairobi"),
            ("KE-31", "Nakuru"), ("KE-32", "Nandi"), ("KE-33", "Narok"),
            ("KE-34", "Nyamira"), ("KE-35", "Nyandarua"), ("KE-36", "Nyeri"),
            ("KE-37", "Samburu"), ("KE-38", "Siaya"), ("KE-39", "Taita-Taveta"),
            ("KE-40", "Tana River"), ("KE-41", "Tharaka-Nithi"), ("KE-42", "Trans Nzoia"),
            ("KE-43", "Turkana"), ("KE-44", "Uasin Gishu"), ("KE-45", "Vihiga"),
            ("KE-46", "Wajir"), ("KE-47", "West Pokot"),
        ],
    },
    "Lesotho": {
        "code": "LS",
        "name": "Lesotho",
        "admin_label": "District",
        "local_label": "Community Council",
        "regions": [
            ("LS-D", "Berea"), ("LS-B", "Butha-Buthe"), ("LS-C", "Leribe"),
            ("LS-E", "Mafeteng"), ("LS-A", "Maseru"), ("LS-F", "Mohale's Hoek"),
            ("LS-J", "Mokhotlong"), ("LS-H", "Qacha's Nek"), ("LS-G", "Quthing"),
            ("LS-K", "Thaba-Tseka"),
        ],
    },
    "Liberia": {
        "code": "LR",
        "name": "Liberia",
        "admin_label": "County",
        "local_label": "District",
        "regions": [
            ("LR-BM", "Bomi"), ("LR-BG", "Bong"), ("LR-GP", "Gbarpolu"),
            ("LR-GB", "Grand Bassa"), ("LR-CM", "Grand Cape Mount"), ("LR-GG", "Grand Gedeh"),
            ("LR-GK", "Grand Kru"), ("LR-LO", "Lofa"), ("LR-MG", "Margibi"),
            ("LR-MY", "Maryland"), ("LR-MO", "Montserrado"), ("LR-NI", "Nimba"),
            ("LR-RI", "River Cess"), ("LR-RG", "River Gee"), ("LR-SI", "Sinoe"),
        ],
    },
    "Libya": {
        "code": "LY",
        "name": "Libya",
        "admin_label": "District",
        "local_label": "Municipality",
        "regions": [
            ("LY-BU", "Al Butnan"), ("LY-JA", "Al Jabal al Akhdar"), ("LY-JG", "Al Jabal al Gharbi"),
            ("LY-JI", "Al Jafara"), ("LY-JU", "Al Jufra"), ("LY-KF", "Al Kufra"),
            ("LY-MJ", "Al Marj"), ("LY-MB", "Al Murqub"), ("LY-WA", "Al Wahat"),
            ("LY-NQ", "An Nuqat al Khams"), ("LY-ZA", "Az Zawiyah"), ("LY-BA", "Benghazi"),
            ("LY-DR", "Derna"), ("LY-GT", "Ghat"), ("LY-MI", "Misrata"),
            ("LY-MQ", "Murzuq"), ("LY-NL", "Nalut"), ("LY-SB", "Sabha"),
            ("LY-SR", "Sirte"), ("LY-TB", "Tripoli"), ("LY-WD", "Wadi al Hayaa"),
            ("LY-WS", "Wadi al Shatii"),
        ],
    },
    "Madagascar": {
        "code": "MG",
        "name": "Madagascar",
        "admin_label": "Region",
        "local_label": "District",
        "regions": [
            ("MG-AL", "Alaotra-Mangoro"), ("MG-AM", "Amoron'i Mania"), ("MG-AN", "Analamanga"),
            ("MG-AF", "Analanjirofo"), ("MG-AD", "Androy"), ("MG-AS", "Anosy"),
            ("MG-AA", "Atsimo-Andrefana"), ("MG-AT", "Atsimo-Atsinanana"), ("MG-AI", "Atsinanana"),
            ("MG-BK", "Betsiboka"), ("MG-BO", "Boeny"), ("MG-BG", "Bongolava"),
            ("MG-DI", "Diana"), ("MG-FI", "Fitovinany"), ("MG-HM", "Haute Matsiatra"),
            ("MG-IH", "Ihorombe"), ("MG-IT", "Itasy"), ("MG-ML", "Melaky"),
            ("MG-ME", "Menabe"), ("MG-SA", "Sava"), ("MG-SO", "Sofia"),
            ("MG-VA", "Vakinankaratra"), ("MG-VT", "Vatovavy"),
        ],
    },
    "Malawi": {
        "code": "MW",
        "name": "Malawi",
        "admin_label": "District",
        "local_label": "Traditional Authority",
        "regions": [
            ("MW-BA", "Balaka"), ("MW-BL", "Blantyre"), ("MW-CK", "Chikwawa"),
            ("MW-CR", "Chiradzulu"), ("MW-CT", "Chitipa"), ("MW-DE", "Dedza"),
            ("MW-DO", "Dowa"), ("MW-KR", "Karonga"), ("MW-KS", "Kasungu"),
            ("MW-LK", "Likoma"), ("MW-LL", "Lilongwe"), ("MW-MC", "Machinga"),
            ("MW-MG", "Mangochi"), ("MW-MCJ", "Mchinji"), ("MW-MU", "Mulanje"),
            ("MW-MW", "Mwanza"), ("MW-MZ", "Mzimba"), ("MW-NE", "Neno"),
            ("MW-NB", "Nkhata Bay"), ("MW-NK", "Nkhotakota"), ("MW-NS", "Nsanje"),
            ("MW-NU", "Ntcheu"), ("MW-NI", "Ntchisi"), ("MW-PH", "Phalombe"),
            ("MW-RU", "Rumphi"), ("MW-SA", "Salima"), ("MW-TH", "Thyolo"),
            ("MW-ZO", "Zomba"),
        ],
    },
    "Mali": {
        "code": "ML",
        "name": "Mali",
        "admin_label": "Region",
        "local_label": "Cercle",
        "regions": [
            ("ML-BKO", "Bamako"), ("ML-BGD", "Bandiagara"), ("ML-BGN", "Bougouni"),
            ("ML-DIO", "Dioïla"), ("ML-DOU", "Douentza"), ("ML-7", "Gao"),
            ("ML-1", "Kayes"), ("ML-8", "Kidal"), ("ML-KIT", "Kita"),
            ("ML-2", "Koulikoro"), ("ML-KTL", "Koutiala"), ("ML-MNK", "Ménaka"),
            ("ML-5", "Mopti"), ("ML-NIO", "Nioro"), ("ML-SAN", "San"),
            ("ML-4", "Ségou"), ("ML-3", "Sikasso"), ("ML-TAO", "Taoudénit"),
            ("ML-TES", "Tessalit"), ("ML-6", "Tombouctou"),
        ],
    },
    "Mauritania": {
        "code": "MR",
        "name": "Mauritania",
        "admin_label": "Region / Wilaya",
        "local_label": "Department / Moughataa",
        "regions": [
            ("MR-07", "Adrar"), ("MR-03", "Assaba"), ("MR-05", "Brakna"),
            ("MR-08", "Dakhlet Nouadhibou"), ("MR-04", "Gorgol"), ("MR-10", "Guidimaka"),
            ("MR-01", "Hodh Ech Chargui"), ("MR-02", "Hodh El Gharbi"), ("MR-12", "Inchiri"),
            ("MR-14", "Nouakchott-Nord"), ("MR-13", "Nouakchott-Ouest"), ("MR-15", "Nouakchott-Sud"),
            ("MR-09", "Tagant"), ("MR-11", "Tiris Zemmour"), ("MR-06", "Trarza"),
        ],
    },
    "Mauritius": {
        "code": "MU",
        "name": "Mauritius",
        "admin_label": "District",
        "local_label": "Village / Ward",
        "regions": [
            ("MU-AG", "Agaléga"), ("MU-BL", "Black River"), ("MU-CC", "Cargados Carajos"),
            ("MU-FL", "Flacq"), ("MU-GP", "Grand Port"), ("MU-MO", "Moka"),
            ("MU-PA", "Pamplemousses"), ("MU-PW", "Plaines Wilhems"), ("MU-PL", "Port Louis"),
            ("MU-RR", "Rivière du Rempart"), ("MU-RO", "Rodrigues"), ("MU-SA", "Savanne"),
        ],
    },
    "Morocco": {
        "code": "MA",
        "name": "Morocco",
        "admin_label": "Region",
        "local_label": "Province / Prefecture",
        "regions": [
            ("MA-05", "Béni Mellal-Khénifra"), ("MA-06", "Casablanca-Settat"),
            ("MA-12", "Dakhla-Oued Ed-Dahab"), ("MA-08", "Drâa-Tafilalet"),
            ("MA-03", "Fès-Meknès"), ("MA-10", "Guelmim-Oued Noun"),
            ("MA-11", "Laâyoune-Sakia El Hamra"), ("MA-07", "Marrakech-Safi"),
            ("MA-02", "Oriental"), ("MA-04", "Rabat-Salé-Kénitra"),
            ("MA-09", "Souss-Massa"), ("MA-01", "Tanger-Tétouan-Al Hoceïma"),
        ],
    },
    "Mozambique": {
        "code": "MZ",
        "name": "Mozambique",
        "admin_label": "Province",
        "local_label": "District",
        "regions": [
            ("MZ-P", "Cabo Delgado"), ("MZ-G", "Gaza"), ("MZ-I", "Inhambane"),
            ("MZ-B", "Manica"), ("MZ-MPM", "Maputo City"), ("MZ-L", "Maputo Province"),
            ("MZ-N", "Nampula"), ("MZ-A", "Niassa"), ("MZ-S", "Sofala"),
            ("MZ-T", "Tete"), ("MZ-Q", "Zambezia"),
        ],
    },
    "Namibia": {
        "code": "NA",
        "name": "Namibia",
        "admin_label": "Region",
        "local_label": "Constituency",
        "regions": [
            ("NA-ER", "Erongo"), ("NA-HA", "Hardap"), ("NA-KA", "ǃKaras"),
            ("NA-KE", "Kavango East"), ("NA-KW", "Kavango West"), ("NA-KH", "Khomas"),
            ("NA-KU", "Kunene"), ("NA-OW", "Ohangwena"), ("NA-OH", "Omaheke"),
            ("NA-OS", "Omusati"), ("NA-ON", "Oshana"), ("NA-OT", "Oshikoto"),
            ("NA-OD", "Otjozondjupa"), ("NA-CA", "Zambezi"),
        ],
    },
    "Niger": {
        "code": "NE",
        "name": "Niger",
        "admin_label": "Region",
        "local_label": "Department",
        "regions": [
            ("NE-1", "Agadez"), ("NE-2", "Diffa"), ("NE-3", "Dosso"),
            ("NE-4", "Maradi"), ("NE-8", "Niamey"), ("NE-5", "Tahoua"),
            ("NE-6", "Tillabéri"), ("NE-7", "Zinder"),
        ],
    },
    "Nigeria": {
        "code": "NG",
        "name": "Nigeria",
        "admin_label": "State / FCT",
        "local_label": "Local Government Area (LGA)",
        "regions": [
            ("NG-AB", "Abia"), ("NG-AD", "Adamawa"), ("NG-AK", "Akwa Ibom"),
            ("NG-AN", "Anambra"), ("NG-BA", "Bauchi"), ("NG-BY", "Bayelsa"),
            ("NG-BE", "Benue"), ("NG-BO", "Borno"), ("NG-CR", "Cross River"),
            ("NG-DE", "Delta"), ("NG-EB", "Ebonyi"), ("NG-ED", "Edo"),
            ("NG-EK", "Ekiti"), ("NG-EN", "Enugu"), ("NG-FC", "FCT (Abuja)"),
            ("NG-GO", "Gombe"), ("NG-IM", "Imo"), ("NG-JI", "Jigawa"),
            ("NG-KD", "Kaduna"), ("NG-KN", "Kano"), ("NG-KT", "Katsina"),
            ("NG-KE", "Kebbi"), ("NG-KO", "Kogi"), ("NG-KW", "Kwara"),
            ("NG-LA", "Lagos"), ("NG-NA", "Nasarawa"), ("NG-NI", "Niger"),
            ("NG-OG", "Ogun"), ("NG-ON", "Ondo"), ("NG-OS", "Osun"),
            ("NG-OY", "Oyo"), ("NG-PL", "Plateau"), ("NG-RI", "Rivers"),
            ("NG-SO", "Sokoto"), ("NG-TA", "Taraba"), ("NG-YO", "Yobe"),
            ("NG-ZA", "Zamfara"),
        ],
    },
    "Rwanda": {
        "code": "RW",
        "name": "Rwanda",
        "admin_label": "Province",
        "local_label": "District",
        "regions": [
            ("RW-02", "Eastern Province"), ("RW-01", "Kigali"),
            ("RW-03", "Northern Province"), ("RW-04", "Southern Province"),
            ("RW-05", "Western Province"),
        ],
    },
    "Sahrawi Arab Democratic Republic": {
        "code": "EH",
        "name": "Sahrawi Arab Democratic Republic",
        "admin_label": "Wilaya",
        "local_label": "Daira",
        "regions": [
            ("EH-AUS", "Auserd"), ("EH-BOU", "Boujdour"), ("EH-DAK", "Dakhla"),
            ("EH-ESM", "Es Semara"), ("EH-LAY", "Laayoune"),
        ],
    },
    "São Tomé and Príncipe": {
        "code": "ST",
        "name": "São Tomé and Príncipe",
        "admin_label": "District",
        "local_label": "Locality",
        "regions": [
            ("ST-AG", "Água Grande"), ("ST-CA", "Cantagalo"), ("ST-CU", "Caué"),
            ("ST-LE", "Lembá"), ("ST-LO", "Lobata"), ("ST-ME", "Mé-Zóchi"),
            ("ST-PR", "Príncipe Autonomous Region"),
        ],
    },
    "Senegal": {
        "code": "SN",
        "name": "Senegal",
        "admin_label": "Region",
        "local_label": "Department",
        "regions": [
            ("SN-DK", "Dakar"), ("SN-DB", "Diourbel"), ("SN-FK", "Fatick"),
            ("SN-KA", "Kaffrine"), ("SN-KL", "Kaolack"), ("SN-KE", "Kédougou"),
            ("SN-KD", "Kolda"), ("SN-LG", "Louga"), ("SN-MT", "Matam"),
            ("SN-SL", "Saint-Louis"), ("SN-SE", "Sédhiou"), ("SN-TC", "Tambacounda"),
            ("SN-TH", "Thiès"), ("SN-ZG", "Ziguinchor"),
        ],
    },
    "Seychelles": {
        "code": "SC",
        "name": "Seychelles",
        "admin_label": "District",
        "local_label": "Sub-district",
        "regions": [
            ("SC-01", "Anse aux Pins"), ("SC-02", "Anse Boileau"), ("SC-03", "Anse Etoile"),
            ("SC-05", "Anse Royale"), ("SC-04", "Au Cap"), ("SC-06", "Baie Lazare"),
            ("SC-07", "Baie Sainte Anne"), ("SC-08", "Beau Vallon"), ("SC-09", "Bel Air"),
            ("SC-10", "Bel Ombre"), ("SC-11", "Cascade"), ("SC-12", "Glacis"),
            ("SC-13", "Grand'Anse Mahé"), ("SC-14", "Grand'Anse Praslin"), ("SC-15", "La Digue"),
            ("SC-16", "La Rivière Anglaise"), ("SC-24", "Les Mamelles"), ("SC-17", "Mont Buxton"),
            ("SC-18", "Mont Fleuri"), ("SC-19", "Plaisance"), ("SC-20", "Pointe La Rue"),
            ("SC-21", "Port Glaud"), ("SC-25", "Roche Caiman"), ("SC-22", "Saint Louis"),
            ("SC-23", "Takamaka"), ("SC-26", "Outer Islands"),
        ],
    },
    "Sierra Leone": {
        "code": "SL",
        "name": "Sierra Leone",
        "admin_label": "Province",
        "local_label": "District",
        "regions": [
            ("SL-E", "Eastern Province"), ("SL-N", "Northern Province"),
            ("SL-NW", "North Western Province"), ("SL-S", "Southern Province"),
            ("SL-W", "Western Area"),
        ],
    },
    "Somalia": {
        "code": "SO",
        "name": "Somalia",
        "admin_label": "State / Region",
        "local_label": "District",
        "regions": [
            ("SO-BN", "Banadir"), ("SO-GA", "Galmudug"), ("SO-HI", "Hirshabelle"),
            ("SO-JU", "Jubaland"), ("SO-PU", "Puntland"), ("SO-SW", "South West"),
        ],
    },
    "South Africa": {
        "code": "ZA",
        "name": "South Africa",
        "admin_label": "Province",
        "local_label": "District / Municipality",
        "regions": [
            ("ZA-EC", "Eastern Cape"), ("ZA-FS", "Free State"), ("ZA-GP", "Gauteng"),
            ("ZA-KZN", "KwaZulu-Natal"), ("ZA-LP", "Limpopo"), ("ZA-MP", "Mpumalanga"),
            ("ZA-NC", "Northern Cape"), ("ZA-NW", "North West"), ("ZA-WC", "Western Cape"),
        ],
    },
    "South Sudan": {
        "code": "SS",
        "name": "South Sudan",
        "admin_label": "State",
        "local_label": "County",
        "regions": [
            ("SS-EC", "Central Equatoria"), ("SS-EE", "Eastern Equatoria"),
            ("SS-JG", "Jonglei"), ("SS-LK", "Lakes"), ("SS-BN", "Northern Bahr el Ghazal"),
            ("SS-UY", "Unity"), ("SS-NU", "Upper Nile"), ("SS-WR", "Warrap"),
            ("SS-BW", "Western Bahr el Ghazal"), ("SS-EW", "Western Equatoria"),
            ("SS-AB", "Abyei Area"), ("SS-PA", "Pibor Area"), ("SS-RA", "Ruweng Area"),
        ],
    },
    "Sudan": {
        "code": "SD",
        "name": "Sudan",
        "admin_label": "State",
        "local_label": "Locality",
        "regions": [
            ("SD-NB", "Blue Nile"), ("SD-DC", "Central Darfur"), ("SD-DE", "East Darfur"),
            ("SD-GD", "Gedaref"), ("SD-GZ", "Gezira"), ("SD-KA", "Kassala"),
            ("SD-KH", "Khartoum"), ("SD-DN", "North Darfur"), ("SD-KN", "North Kordofan"),
            ("SD-NO", "Northern"), ("SD-RS", "Red Sea"), ("SD-NR", "River Nile"),
            ("SD-SI", "Sennar"), ("SD-DS", "South Darfur"), ("SD-KS", "South Kordofan"),
            ("SD-DW", "West Darfur"), ("SD-KW", "West Kordofan"), ("SD-NW", "White Nile"),
        ],
    },
    "Tanzania": {
        "code": "TZ",
        "name": "Tanzania",
        "admin_label": "Region",
        "local_label": "District",
        "regions": [
            ("TZ-01", "Arusha"), ("TZ-02", "Dar es Salaam"), ("TZ-03", "Dodoma"),
            ("TZ-04", "Geita"), ("TZ-05", "Iringa"), ("TZ-06", "Kagera"),
            ("TZ-07", "Katavi"), ("TZ-08", "Kigoma"), ("TZ-09", "Kilimanjaro"),
            ("TZ-10", "Lindi"), ("TZ-11", "Manyara"), ("TZ-12", "Mara"),
            ("TZ-13", "Mbeya"), ("TZ-14", "Morogoro"), ("TZ-15", "Mtwara"),
            ("TZ-16", "Mwanza"), ("TZ-17", "Njombe"), ("TZ-18", "Pemba North"),
            ("TZ-19", "Pemba South"), ("TZ-20", "Pwani"), ("TZ-21", "Rukwa"),
            ("TZ-22", "Ruvuma"), ("TZ-23", "Shinyanga"), ("TZ-24", "Simiyu"),
            ("TZ-25", "Singida"), ("TZ-26", "Songwe"), ("TZ-27", "Tabora"),
            ("TZ-28", "Tanga"), ("TZ-29", "Zanzibar North"), ("TZ-30", "Zanzibar South"),
            ("TZ-31", "Zanzibar Urban/West"),
        ],
    },
    "Togo": {
        "code": "TG",
        "name": "Togo",
        "admin_label": "Region",
        "local_label": "Prefecture",
        "regions": [
            ("TG-C", "Centrale"), ("TG-K", "Kara"), ("TG-M", "Maritime"),
            ("TG-P", "Plateaux"), ("TG-S", "Savanes"),
        ],
    },
    "Tunisia": {
        "code": "TN",
        "name": "Tunisia",
        "admin_label": "Governorate",
        "local_label": "Delegation",
        "regions": [
            ("TN-12", "Ariana"), ("TN-31", "Béja"), ("TN-13", "Ben Arous"),
            ("TN-23", "Bizerte"), ("TN-81", "Gabès"), ("TN-71", "Gafsa"),
            ("TN-32", "Jendouba"), ("TN-41", "Kairouan"), ("TN-42", "Kasserine"),
            ("TN-73", "Kébili"), ("TN-33", "Kef"), ("TN-53", "Mahdia"),
            ("TN-14", "Manouba"), ("TN-82", "Médenine"), ("TN-52", "Monastir"),
            ("TN-21", "Nabeul"), ("TN-61", "Sfax"), ("TN-43", "Sidi Bouzid"),
            ("TN-34", "Siliana"), ("TN-51", "Sousse"), ("TN-83", "Tataouine"),
            ("TN-72", "Tozeur"), ("TN-11", "Tunis"), ("TN-22", "Zaghouan"),
        ],
    },
    "Uganda": {
        "code": "UG",
        "name": "Uganda",
        "admin_label": "Region",
        "local_label": "District",
        "regions": [
            ("UG-C", "Central"), ("UG-E", "Eastern"), ("UG-N", "Northern"),
            ("UG-W", "Western"),
        ],
    },
    "Zambia": {
        "code": "ZM",
        "name": "Zambia",
        "admin_label": "Province",
        "local_label": "District",
        "regions": [
            ("ZM-02", "Central"), ("ZM-08", "Copperbelt"), ("ZM-03", "Eastern"),
            ("ZM-04", "Luapula"), ("ZM-09", "Lusaka"), ("ZM-10", "Muchinga"),
            ("ZM-05", "Northern"), ("ZM-06", "North-Western"), ("ZM-07", "Southern"),
            ("ZM-01", "Western"),
        ],
    },
    "Zimbabwe": {
        "code": "ZW",
        "name": "Zimbabwe",
        "admin_label": "Province",
        "local_label": "District",
        "regions": [
            ("ZW-BU", "Bulawayo"), ("ZW-HA", "Harare"), ("ZW-MA", "Manicaland"),
            ("ZW-MC", "Mashonaland Central"), ("ZW-ME", "Mashonaland East"),
            ("ZW-MW", "Mashonaland West"), ("ZW-MV", "Masvingo"),
            ("ZW-MN", "Matabeleland North"), ("ZW-MS", "Matabeleland South"),
            ("ZW-MI", "Midlands"),
        ],
    },
}

# Aliases and normalization index for lookup resilience
COUNTRY_ALIASES = {
    "côte d'ivoire": "Côte d'Ivoire",
    "cote d'ivoire": "Côte d'Ivoire",
    "congo": "Congo (Republic of the)",
    "republic of the congo": "Congo (Republic of the)",
    "congo (republic of the)": "Congo (Republic of the)",
    "congo-brazzaville": "Congo (Republic of the)",
    "democratic republic of the congo": "Congo (Democratic Republic of the)",
    "dr congo": "Congo (Democratic Republic of the)",
    "congo (democratic republic of the)": "Congo (Democratic Republic of the)",
    "congo-kinshasa": "Congo (Democratic Republic of the)",
    "drc": "Congo (Democratic Republic of the)",
    "cabo verde": "Cabo Verde",
    "cape verde": "Cabo Verde",
    "eswatini": "Eswatini",
    "swaziland": "Eswatini",
    "sao tome and principe": "São Tomé and Príncipe",
    "são tomé and príncipe": "São Tomé and Príncipe",
    "western sahara": "Sahrawi Arab Democratic Republic",
    "sahrawi arab democratic republic": "Sahrawi Arab Democratic Republic",
}


# Decorate countries with ISO3, ISO2, source metadata, and normalized label aliases
for _cname, _cdata in AFRICAN_COUNTRIES.items():
    _code = _cdata["code"].upper()
    from .geography_catalogue import ISO2_TO_ISO3, get_source_for_country
    _iso3 = ISO2_TO_ISO3.get(_code, _code)
    _src = get_source_for_country(_iso3)
    _cdata["iso3"] = _iso3
    _cdata["iso2"] = _code
    _cdata["admin1_label"] = _cdata["admin_label"]
    _cdata["admin2_label"] = _cdata["local_label"]
    _cdata["source"] = _src["name"]
    _cdata["source_version"] = _src["version"]
    _cdata["last_verified_date"] = _src["last_verified_date"]


def get_country(identifier):
    """Lookup country record by ISO3, ISO2, or name (case-insensitive)."""
    if not identifier:
        return None
    ident = str(identifier).strip()
    # Check exact name
    if ident in AFRICAN_COUNTRIES:
        return AFRICAN_COUNTRIES[ident]
    ident_upper = ident.upper()
    # Check by 3-letter ISO3 or 2-letter ISO2 code
    for country in AFRICAN_COUNTRIES.values():
        if country.get("iso3") == ident_upper or country["code"].upper() == ident_upper:
            return country
    # Check case-insensitive name or alias
    ident_lower = ident.lower()
    canonical = COUNTRY_ALIASES.get(ident_lower)
    if canonical and canonical in AFRICAN_COUNTRIES:
        return AFRICAN_COUNTRIES[canonical]
    for name, country in AFRICAN_COUNTRIES.items():
        if name.lower() == ident_lower:
            return country
    return None


def get_african_countries_choices():
    """Return sorted (name, name) tuples for all 55 countries."""
    return sorted([(c["name"], c["name"]) for c in AFRICAN_COUNTRIES.values()], key=lambda x: x[0])


def get_country_regions(country_identifier):
    """Return list of (name, name) tuples for regions of a given country."""
    country = get_country(country_identifier)
    if not country:
        return []
    return [(r[1], r[1]) for r in country["regions"]]


def find_region_in_country(country_identifier, region_identifier):
    """Lookup region in a given country by code or name."""
    country = get_country(country_identifier)
    if not country or not region_identifier:
        return None
    reg_id = str(region_identifier).strip()
    reg_id_upper = reg_id.upper()
    reg_id_lower = reg_id.lower()
    for code, name in country["regions"]:
        if code.upper() == reg_id_upper or name.lower() == reg_id_lower:
            return {"code": code, "name": name}
        # Allow special alias like FCT for FCT (Abuja)
        if name == "FCT (Abuja)" and reg_id_upper in ("FCT", "ABUJA", "FCT (ABUJA)"):
            return {"code": code, "name": name}
    return None


# ==============================================================================
# IANA Timezone Data for African Countries (Complies with standard zoneinfo)
# ==============================================================================

DEFAULT_COUNTRY_TIMEZONES = {
    # 2-letter ISO 3166-1 codes
    "DZ": "Africa/Algiers",
    "AO": "Africa/Luanda",
    "BJ": "Africa/Porto-Novo",
    "BW": "Africa/Gaborone",
    "BF": "Africa/Ouagadougou",
    "BI": "Africa/Bujumbura",
    "CV": "Atlantic/Cape_Verde",
    "CM": "Africa/Douala",
    "CF": "Africa/Bangui",
    "TD": "Africa/Ndjamena",
    "KM": "Indian/Comoro",
    "CG": "Africa/Brazzaville",
    "CD": "Africa/Kinshasa",
    "CI": "Africa/Abidjan",
    "DJ": "Africa/Djibouti",
    "EG": "Africa/Cairo",
    "GQ": "Africa/Malabo",
    "ER": "Africa/Asmara",
    "SZ": "Africa/Mbabane",
    "ET": "Africa/Addis_Ababa",
    "GA": "Africa/Libreville",
    "GM": "Africa/Banjul",
    "GH": "Africa/Accra",
    "GN": "Africa/Conakry",
    "GW": "Africa/Bissau",
    "KE": "Africa/Nairobi",
    "LS": "Africa/Maseru",
    "LR": "Africa/Monrovia",
    "LY": "Africa/Tripoli",
    "MG": "Indian/Antananarivo",
    "MW": "Africa/Blantyre",
    "ML": "Africa/Bamako",
    "MR": "Africa/Nouakchott",
    "MU": "Indian/Mauritius",
    "MA": "Africa/Casablanca",
    "MZ": "Africa/Maputo",
    "NA": "Africa/Windhoek",
    "NE": "Africa/Niamey",
    "NG": "Africa/Lagos",
    "RW": "Africa/Kigali",
    "EH": "Africa/El_Aaiun",
    "ST": "Africa/Sao_Tome",
    "SN": "Africa/Dakar",
    "SC": "Indian/Mahe",
    "SL": "Africa/Freetown",
    "SO": "Africa/Mogadishu",
    "ZA": "Africa/Johannesburg",
    "SS": "Africa/Juba",
    "SD": "Africa/Khartoum",
    "TZ": "Africa/Dar_es_Salaam",
    "TG": "Africa/Lome",
    "TN": "Africa/Tunis",
    "UG": "Africa/Kampala",
    "ZM": "Africa/Lusaka",
    "ZW": "Africa/Harare",

    # Canonical full names
    "Algeria": "Africa/Algiers",
    "Angola": "Africa/Luanda",
    "Benin": "Africa/Porto-Novo",
    "Botswana": "Africa/Gaborone",
    "Burkina Faso": "Africa/Ouagadougou",
    "Burundi": "Africa/Bujumbura",
    "Cabo Verde": "Atlantic/Cape_Verde",
    "Cameroon": "Africa/Douala",
    "Central African Republic": "Africa/Bangui",
    "Chad": "Africa/Ndjamena",
    "Comoros": "Indian/Comoro",
    "Congo (Republic of the)": "Africa/Brazzaville",
    "Congo (Democratic Republic of the)": "Africa/Kinshasa",
    "Côte d'Ivoire": "Africa/Abidjan",
    "Djibouti": "Africa/Djibouti",
    "Egypt": "Africa/Cairo",
    "Equatorial Guinea": "Africa/Malabo",
    "Eritrea": "Africa/Asmara",
    "Eswatini": "Africa/Mbabane",
    "Ethiopia": "Africa/Addis_Ababa",
    "Gabon": "Africa/Libreville",
    "Gambia": "Africa/Banjul",
    "Ghana": "Africa/Accra",
    "Guinea": "Africa/Conakry",
    "Guinea-Bissau": "Africa/Bissau",
    "Kenya": "Africa/Nairobi",
    "Lesotho": "Africa/Maseru",
    "Liberia": "Africa/Monrovia",
    "Libya": "Africa/Tripoli",
    "Madagascar": "Indian/Antananarivo",
    "Malawi": "Africa/Blantyre",
    "Mali": "Africa/Bamako",
    "Mauritania": "Africa/Nouakchott",
    "Mauritius": "Indian/Mauritius",
    "Morocco": "Africa/Casablanca",
    "Mozambique": "Africa/Maputo",
    "Namibia": "Africa/Windhoek",
    "Niger": "Africa/Niamey",
    "Nigeria": "Africa/Lagos",
    "Rwanda": "Africa/Kigali",
    "Sahrawi Arab Democratic Republic": "Africa/El_Aaiun",
    "São Tomé and Príncipe": "Africa/Sao_Tome",
    "Senegal": "Africa/Dakar",
    "Seychelles": "Indian/Mahe",
    "Sierra Leone": "Africa/Freetown",
    "Somalia": "Africa/Mogadishu",
    "South Africa": "Africa/Johannesburg",
    "South Sudan": "Africa/Juba",
    "Sudan": "Africa/Khartoum",
    "Tanzania": "Africa/Dar_es_Salaam",
    "Togo": "Africa/Lome",
    "Tunisia": "Africa/Tunis",
    "Uganda": "Africa/Kampala",
    "Zambia": "Africa/Lusaka",
    "Zimbabwe": "Africa/Harare",
}

# Multi-timezone country definitions.
# The Democratic Republic of the Congo (CD) spans two IANA time zones:
# 1. West Africa Time (UTC+1, Africa/Kinshasa) for western provinces.
# 2. Central Africa Time (UTC+2, Africa/Lubumbashi) for eastern provinces.
MULTI_TIMEZONE_COUNTRIES = {
    "CD": {
        "name": "Congo (Democratic Republic of the)",
        "default": "Africa/Kinshasa",
        "timezones": ["Africa/Kinshasa", "Africa/Lubumbashi"],
        "region_timezones": {
            # Western provinces (UTC+1 / Africa/Kinshasa)
            "CD-KN": "Africa/Kinshasa", "Kinshasa": "Africa/Kinshasa",
            "CD-BC": "Africa/Kinshasa", "Kongo Central": "Africa/Kinshasa",
            "CD-KG": "Africa/Kinshasa", "Kwango": "Africa/Kinshasa",
            "CD-KL": "Africa/Kinshasa", "Kwilu": "Africa/Kinshasa",
            "CD-MN": "Africa/Kinshasa", "Mai-Ndombe": "Africa/Kinshasa",
            "CD-EQ": "Africa/Kinshasa", "Équateur": "Africa/Kinshasa", "Equateur": "Africa/Kinshasa",
            "CD-MO": "Africa/Kinshasa", "Mongala": "Africa/Kinshasa",
            "CD-NU": "Africa/Kinshasa", "Nord-Ubangi": "Africa/Kinshasa",
            "CD-SU": "Africa/Kinshasa", "Sud-Ubangi": "Africa/Kinshasa",
            "CD-TU": "Africa/Kinshasa", "Tshuapa": "Africa/Kinshasa",

            # Eastern provinces (UTC+2 / Africa/Lubumbashi)
            "CD-BU": "Africa/Lubumbashi", "Bas-Uélé": "Africa/Lubumbashi", "Bas-Uele": "Africa/Lubumbashi",
            "CD-HK": "Africa/Lubumbashi", "Haut-Katanga": "Africa/Lubumbashi",
            "CD-HL": "Africa/Lubumbashi", "Haut-Lomami": "Africa/Lubumbashi",
            "CD-HU": "Africa/Lubumbashi", "Haut-Uélé": "Africa/Lubumbashi", "Haut-Uele": "Africa/Lubumbashi",
            "CD-IT": "Africa/Lubumbashi", "Ituri": "Africa/Lubumbashi",
            "CD-KS": "Africa/Lubumbashi", "Kasaï": "Africa/Lubumbashi", "Kasai": "Africa/Lubumbashi",
            "CD-KC": "Africa/Lubumbashi", "Kasaï-Central": "Africa/Lubumbashi", "Kasai-Central": "Africa/Lubumbashi",
            "CD-KO": "Africa/Lubumbashi", "Kasaï-Oriental": "Africa/Lubumbashi", "Kasai-Oriental": "Africa/Lubumbashi",
            "CD-LO": "Africa/Lubumbashi", "Lomami": "Africa/Lubumbashi",
            "CD-LU": "Africa/Lubumbashi", "Lualaba": "Africa/Lubumbashi",
            "CD-MA": "Africa/Lubumbashi", "Maniema": "Africa/Lubumbashi",
            "CD-NK": "Africa/Lubumbashi", "Nord-Kivu": "Africa/Lubumbashi",
            "CD-SA": "Africa/Lubumbashi", "Sankuru": "Africa/Lubumbashi",
            "CD-SK": "Africa/Lubumbashi", "Sud-Kivu": "Africa/Lubumbashi",
            "CD-TA": "Africa/Lubumbashi", "Tanganyika": "Africa/Lubumbashi",
            "CD-TO": "Africa/Lubumbashi", "Tshopo": "Africa/Lubumbashi",
        },
    },
}
MULTI_TIMEZONE_COUNTRIES["Congo (Democratic Republic of the)"] = MULTI_TIMEZONE_COUNTRIES["CD"]


def get_country_default_timezone(country_identifier):
    """Return default IANA timezone for a given country code or name."""
    country = get_country(country_identifier)
    if not country:
        return None
    code = country["code"].upper()
    name = country["name"]
    return DEFAULT_COUNTRY_TIMEZONES.get(code) or DEFAULT_COUNTRY_TIMEZONES.get(name)


def get_country_timezones(country_identifier):
    """Return all valid IANA timezones for a given country."""
    country = get_country(country_identifier)
    if not country:
        return []
    code = country["code"].upper()
    if code in MULTI_TIMEZONE_COUNTRIES:
        return list(MULTI_TIMEZONE_COUNTRIES[code]["timezones"])
    default_tz = get_country_default_timezone(code)
    return [default_tz] if default_tz else []


def is_multi_timezone_country(country_identifier):
    """Check if country has multiple distinct time zones."""
    country = get_country(country_identifier)
    if not country:
        return False
    return country["code"].upper() in MULTI_TIMEZONE_COUNTRIES


def resolve_timezone_for_location(country_identifier, region_identifier=None, current_timezone=None, has_manual_override=False):
    """
    Deterministically resolve the IANA timezone for a country and optional region.
    - If has_manual_override is True and current_timezone is given, preserves explicit user choice.
    - Otherwise, returns the country's agreed default timezone.
    - For multi-timezone countries (e.g. DRC), resolves according to region/province.
    """
    if has_manual_override and current_timezone:
        return current_timezone

    country = get_country(country_identifier)
    if not country:
        return current_timezone or "UTC"

    code = country["code"].upper()
    if code in MULTI_TIMEZONE_COUNTRIES:
        multi_cfg = MULTI_TIMEZONE_COUNTRIES[code]
        if region_identifier:
            reg_match = find_region_in_country(code, region_identifier)
            reg_key = reg_match["name"] if reg_match else str(region_identifier).strip()
            reg_tz = multi_cfg["region_timezones"].get(reg_key)
            if not reg_tz and reg_match:
                reg_tz = multi_cfg["region_timezones"].get(reg_match["code"])
            if not reg_tz:
                reg_lower = reg_key.lower()
                for k, tz in multi_cfg["region_timezones"].items():
                    if k.lower() == reg_lower:
                        reg_tz = tz
                        break
            if reg_tz:
                return reg_tz
        return multi_cfg["default"]

    default_tz = get_country_default_timezone(code)
    return default_tz or current_timezone or "UTC"


def format_user_datetime(dt, tz_name=None, fmt="c"):
    """
    Format datetime consistently using the user's active/persisted timezone or specified timezone.
    Consistently formats dates, reminders, and timestamps across the platform.
    """
    if not dt:
        return ""
    import zoneinfo
    from django.utils import timezone

    tz = None
    if tz_name:
        try:
            tz = zoneinfo.ZoneInfo(tz_name)
        except Exception:
            pass
    if tz:
        try:
            local_dt = timezone.localtime(dt, tz)
        except Exception:
            local_dt = dt.astimezone(tz) if hasattr(dt, "astimezone") else dt
    else:
        try:
            local_dt = timezone.localtime(dt)
        except Exception:
            local_dt = dt
    try:
        from django.template.defaultfilters import date as django_date
        res = django_date(local_dt, fmt)
        if res:
            return res
    except Exception:
        pass
    return local_dt.isoformat()


