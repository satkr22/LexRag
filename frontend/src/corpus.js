// Presentation-friendly copy of docs/doc_list.py for the React corpus browser.
export const ACT_CATEGORIES = [
  {
    name: "Constitutional, Governance & Access to Justice",
    acts: [
      "Constitution of India",
      "Right to Information Act, 2005",
      "Legal Services Authorities Act, 1987",
      "Protection of Human Rights Act, 1993",
    ],
  },
  {
    name: "Criminal Law, Procedure & Evidence",
    acts: [
      "Bharatiya Nyaya Sanhita, 2023",
      "Bharatiya Nagarik Suraksha Sanhita, 2023",
      "Bharatiya Sakshya Adhiniyam, 2023",
      "SC/ST (Prevention of Atrocities) Act, 1989",
      "Prevention of Corruption Act, 1988",
    ],
  },
  {
    name: "Civil Procedure, Remedies & Dispute Resolution",
    acts: [
      "Code of Civil Procedure, 1908",
      "Limitation Act, 1963",
      "Consumer Protection Act, 2019",
      "Arbitration and Conciliation Act, 1996",
      "Specific Relief Act, 1963",
    ],
  },
  {
    name: "Contracts, Commerce & Corporate Law",
    acts: [
      "Indian Contract Act, 1872",
      "Companies Act, 2013",
      "Insolvency and Bankruptcy Code, 2016",
      "Negotiable Instruments Act, 1881",
      "Sale of Goods Act, 1930",
      "Indian Partnership Act, 1932",
      "Limited Liability Partnership Act, 2008",
    ],
  },
  {
    name: "Family, Marriage & Succession",
    acts: [
      "Hindu Marriage Act, 1955",
      "Hindu Succession Act, 1956",
      "Special Marriage Act, 1954",
      "Family Courts Act, 1984",
      "Indian Succession Act, 1925",
    ],
  },
  {
    name: "Property, Registration & Easements",
    acts: [
      "Transfer of Property Act, 1882",
      "Registration Act, 1908",
      "Indian Easements Act, 1882",
    ],
  },
  {
    name: "Taxation",
    acts: [
      "Central Goods and Services Tax Act, 2017",
      "Income-tax Acts, 2025 and 1961",
    ],
  },
  {
    name: "Digital, Cyber & Data Protection",
    acts: [
      "Information Technology Act, 2000",
      "Digital Personal Data Protection Act, 2023",
    ],
  },
  {
    name: "Social Protection, Child Rights & Education",
    acts: [
      "Protection of Children from Sexual Offences Act, 2012",
      "Protection of Women from Domestic Violence Act, 2005",
      "Dowry Prohibition Act, 1961",
      "Rights of Persons with Disabilities Act, 2016",
      "Juvenile Justice (Care and Protection of Children) Act, 2015",
      "Maintenance and Welfare of Parents and Senior Citizens Act, 2007",
      "Right of Children to Free and Compulsory Education Act, 2009",
    ],
  },
  { name: "Transport & Road Safety", acts: ["Motor Vehicles Act, 1988"] },
];

export const ACT_COUNT = ACT_CATEGORIES.reduce(
  (count, category) => count + category.acts.length,
  0,
);
