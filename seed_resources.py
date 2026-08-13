#!/usr/bin/env python3
import sys
from pathlib import Path
from database import SessionLocal, StudyMaterial, VideoMaterial, Flashcard, CuratedSet, Question

def seed_resources():
    db = SessionLocal()
    try:
        # Clear existing data to prevent duplicates
        print("Clearing existing resources...")
        db.query(StudyMaterial).delete()
        db.query(VideoMaterial).delete()
        db.query(Flashcard).delete()
        db.query(CuratedSet).delete()
        db.commit()

        # ============================================================
        # 1. SEED STUDY MATERIALS
        # ============================================================
        print("Seeding Study Materials...")
        materials = [
            # GATE CS - Topics
            StudyMaterial(
                subject="CS",
                topic="General Aptitude",
                subtopic="Quantitative Aptitude",
                title="Quantitative Aptitude for Competitive Examinations (Aggarwal)",
                url="https://www.schandpublishing.com/books/competitive-exams/quantitative-aptitude-for-competitive-examinations/9789352535323/",
                type="Book",
                description="Comprehensive practice handbook for logical reasoning and quantitative analysis.",
                is_verified=True
            ),
            StudyMaterial(
                subject="CS",
                topic="Engineering Mathematics",
                subtopic="Linear Algebra & Calculus",
                title="Higher Engineering Mathematics (B.S. Grewal)",
                url="http://www.bsgrewal.com/",
                type="Book",
                description="Standard textbook covering algebra, calculus, and differential equations for engineering.",
                is_verified=True
            ),
            StudyMaterial(
                subject="CS",
                topic="Discrete Mathematics",
                subtopic="Mathematical Logic & Graphs",
                title="Discrete Mathematics and its Applications (Kenneth Rosen)",
                url="https://www.mheducation.com/highered/product/discrete-mathematics-its-applications-rosen/M9781259676512.html",
                type="Book",
                description="Excellent comprehensive guide on sets, combinatorics, logic, and graph theory.",
                is_verified=True
            ),
            StudyMaterial(
                subject="CS",
                topic="Digital Logic",
                subtopic="Logic Gates & Minimization",
                title="Digital Design (M. Morris Mano)",
                url="https://www.pearson.com/us/higher-education/program/Mano-Digital-Design-With-an-Introduction-to-the-Verilog-HDL-VHDL-and-System-Verilog-6th-Edition/PGM334823.html",
                type="Book",
                description="Fundamental textbook for Boolean algebra, logic minimization, and sequential circuits.",
                is_verified=True
            ),
            StudyMaterial(
                subject="CS",
                topic="Computer Organization and Architecture (COA)",
                subtopic="CPU & Memory Systems",
                title="Computer Organization (Carl Hamacher)",
                url="https://www.mheducation.com/highered/product/computer-organization-embedded-systems-hamacher/M0073380652.html",
                type="Book",
                description="Standard reference book for CPU architecture, pipelining, and memory hierarchy.",
                is_verified=True
            ),
            StudyMaterial(
                subject="CS",
                topic="Programming and Data Structures",
                subtopic="C Programming & Basics",
                title="The C Programming Language (Kernighan & Ritchie)",
                url="https://www.pearson.com/en-us/subject-catalog/p/c-programming-language/P200000003154/9780131103627",
                type="Book",
                description="The ultimate standard reference book for C syntax, pointers, and memory layout.",
                is_verified=True
            ),
            StudyMaterial(
                subject="CS",
                topic="Algorithms",
                subtopic="Complexity & Sorting",
                title="Introduction to Algorithms (CLRS)",
                url="https://mitpress.mit.edu/9780262033848/introduction-to-algorithms/",
                type="Book",
                description="Gold standard reference covering asymptotic bounds, greedy methods, dynamic programming, and graphs.",
                is_verified=True
            ),
            StudyMaterial(
                subject="CS",
                topic="Theory of Computation (TOC)",
                subtopic="Automata & Decidability",
                title="Introduction to Automata Theory, Languages, and Computation (Ullman)",
                url="https://www.pearson.com/us/higher-education/program/Hopcroft-Introduction-to-Automata-Theory-Languages-and-Computation-3rd-Edition/PGM244439.html",
                type="Book",
                description="Definitive textbook covering regular languages, context-free grammars, Turing machines, and decidability.",
                is_verified=True
            ),
            StudyMaterial(
                subject="CS",
                topic="Compiler Design",
                subtopic="Syntax Analysis & Parsing",
                title="Compilers: Principles, Techniques, and Tools (Dragon Book)",
                url="https://www.pearson.com/us/higher-education/program/Aho-Compilers-Principles-Techniques-and-Tools-2nd-Edition/PGM278453.html",
                type="Book",
                description="Standard reference on lexical analysis, LL/LR parsers, syntax-directed translation, and optimization.",
                is_verified=True
            ),
            StudyMaterial(
                subject="CS",
                topic="Operating Systems (OS)",
                subtopic="Memory & Threads",
                title="Operating System Concepts (Galvin)",
                url="https://www.os-book.com/OS10/",
                type="Book",
                description="Comprehensive reference covering process scheduling, semaphores, virtual memory, and deadlocks.",
                is_verified=True
            ),
            StudyMaterial(
                subject="CS",
                topic="Databases (DBMS)",
                subtopic="Relational Model & Normalization",
                title="Database System Concepts (Korth)",
                url="https://www.db-book.com/",
                type="Book",
                description="Industry standard book for SQL syntax, relational algebra, normal forms (1NF-BCNF), and transactions.",
                is_verified=True
            ),
            StudyMaterial(
                subject="CS",
                topic="Computer Networks (CN)",
                subtopic="TCP/IP Layers & Protocols",
                title="Computer Networking: A Top-Down Approach (Kurose & Ross)",
                url="https://www.pearson.com/en-us/subject-catalog/p/computer-networking/P200000003328/9780136683889",
                type="Book",
                description="Top-down guide covering Application, Transport, Network, and Link layers protocols.",
                is_verified=True
            ),

            # GATE DA - Topics
            StudyMaterial(
                subject="DA",
                topic="General Aptitude",
                subtopic="Aptitude & Logic",
                title="Quantitative Aptitude for GATE (Aggarwal)",
                url="https://www.schandpublishing.com/books/competitive-exams/quantitative-aptitude-for-competitive-examinations/9789352535323/",
                type="Book",
                description="Aptitude and verbal reasoning question banks mapped for GATE candidates.",
                is_verified=True
            ),
            StudyMaterial(
                subject="DA",
                topic="Linear Algebra",
                subtopic="Eigenvalues & Spaces",
                title="Introduction to Linear Algebra (Gilbert Strang)",
                url="https://math.mit.edu/~gs/linearalgebra/",
                type="Book",
                description="Legendary linear algebra textbook covering matrix geometry, projections, determinants, and SVD.",
                is_verified=True
            ),
            StudyMaterial(
                subject="DA",
                topic="Calculus and Optimization",
                subtopic="Gradients & Optimization",
                title="Thomas' Calculus (Thomas)",
                url="https://www.pearson.com/us/higher-education/program/Weir-Thomas-Calculus-14th-Edition/PGM2857731.html",
                type="Book",
                description="Mathematical calculus resource for limits, derivatives, integrals, and gradient optimizations.",
                is_verified=True
            ),
            StudyMaterial(
                subject="DA",
                topic="Probability and Statistics",
                subtopic="Distributions & Bayes",
                title="A First Course in Probability (Sheldon Ross)",
                url="https://www.pearson.com/en-us/subject-catalog/p/first-course-in-probability-a/P200000003290/9780134753119",
                type="Book",
                description="Intuitive guide covering conditional probability, random variables, and variance models.",
                is_verified=True
            ),
            StudyMaterial(
                subject="DA",
                topic="Python Programming and Data Structures",
                subtopic="Python Basics & Structs",
                title="Official Python Tutorial and Documentation",
                url="https://docs.python.org/3/tutorial/",
                type="Link",
                description="Official developer tutorial for lists, dicts, OOP, and data structures.",
                is_verified=True
            ),
            StudyMaterial(
                subject="DA",
                topic="Algorithms",
                subtopic="Complexity Bounds",
                title="Introduction to Algorithms (CLRS) - DA Focus",
                url="https://mitpress.mit.edu/9780262033848/introduction-to-algorithms/",
                type="Book",
                description="Recommended chapters mapping Big O, divide & conquer, and sorting methods.",
                is_verified=True
            ),
            StudyMaterial(
                subject="DA",
                topic="Database Management and Warehousing",
                subtopic="SQL & Data Warehousing",
                title="Database Management Systems (Raghu Ramakrishnan)",
                url="https://www.mheducation.com/highered/product/database-management-systems-ramakrishnan-gehrke/M9780072465631.html",
                type="Book",
                description="Relational database textbook focusing on relational calculus, SQL, schema design, and OLAP warehousing.",
                is_verified=True
            ),
            StudyMaterial(
                subject="DA",
                topic="Machine Learning (ML)",
                subtopic="Supervised Models",
                title="An Introduction to Statistical Learning (ISL)",
                url="https://www.statlearning.com/",
                type="Book",
                description="Leading ML book detailing linear models, SVMs, tree classification, clustering, and neural networks.",
                is_verified=True
            ),
            StudyMaterial(
                subject="DA",
                topic="Artificial Intelligence (AI)",
                subtopic="Search & Logic",
                title="Artificial Intelligence: A Modern Approach (Russell & Norvig)",
                url="http://aima.cs.berkeley.edu/",
                type="Book",
                description="The standard AI handbook detailing search trees, heuristic bounds, and Bayesian networks.",
                is_verified=True
            )
        ]
        db.add_all(materials)
        db.commit()

        # ============================================================
        # 2. SEED VIDEO LECTURES
        # ============================================================
        print("Seeding Video Lectures...")
        videos = [
            # GATE CS - General Aptitude
            VideoMaterial(
                subject="CS",
                topic="General Aptitude",
                subtopic="Quantitative Methods",
                title="GATE General Aptitude Crash Course",
                youtube_url="https://www.youtube.com/watch?v=A4XyP4S5sBE",
                video_id="A4XyP4S5sBE",
                duration_mins=45,
                channel_name="Gate Smashers",
                description="Logical tricks, probability puzzles, and quantitative aptitude formulas for competitive exams."
            ),
            # GATE CS - Engineering Mathematics
            VideoMaterial(
                subject="CS",
                topic="Engineering Mathematics",
                subtopic="Linear Algebra & Systems",
                title="Engineering Mathematics GATE Lectures",
                youtube_url="https://www.youtube.com/watch?v=gG9k5oGkC1o",
                video_id="gG9k5oGkC1o",
                duration_mins=30,
                channel_name="Gate Smashers",
                description="Matrices operations, determinants properties, and linear systems solutions for GATE."
            ),
            # GATE CS - Discrete Math
            VideoMaterial(
                subject="CS",
                topic="Discrete Mathematics",
                subtopic="Set Theory & Logic",
                title="Discrete Mathematics GATE Lectures",
                youtube_url="https://www.youtube.com/watch?v=wG2E2Xk1f6Q",
                video_id="wG2E2Xk1f6Q",
                duration_mins=25,
                channel_name="Gate Smashers",
                description="Detailed guide covering propositions logic, set theory, and truth tables."
            ),
            # GATE CS - Digital Logic
            VideoMaterial(
                subject="CS",
                topic="Digital Logic",
                subtopic="K-Map Minimization",
                title="Digital Logic K-Map Simplification",
                youtube_url="https://www.youtube.com/watch?v=J8D3Q9fC1Yg",
                video_id="J8D3Q9fC1Yg",
                duration_mins=22,
                channel_name="Gate Smashers",
                description="Step-by-step Karnaugh Map (K-Map) simplification logic for Boolean equations."
            ),
            # GATE CS - COA
            VideoMaterial(
                subject="CS",
                topic="Computer Organization and Architecture (COA)",
                subtopic="Cache Mapping",
                title="Computer Organization Cache Memory Mapping",
                youtube_url="https://www.youtube.com/watch?v=8D3Q2fK0sD4",
                video_id="8D3Q2fK0sD4",
                duration_mins=28,
                channel_name="Gate Smashers",
                description="Direct mapping, associative mapping, and set-associative cache structures explained."
            ),
            # GATE CS - Data Structures
            VideoMaterial(
                subject="CS",
                topic="Programming and Data Structures",
                subtopic="Binary Trees",
                title="Data Structures: Binary Trees Traversals",
                youtube_url="https://www.youtube.com/watch?v=9D3QfC8Yg90",
                video_id="9D3QfC8Yg90",
                duration_mins=20,
                channel_name="Gate Smashers",
                description="Inorder, preorder, and postorder traversals of binary search trees with code visualization."
            ),
            # GATE CS - Algorithms
            VideoMaterial(
                subject="CS",
                topic="Algorithms",
                subtopic="Complexity Analysis",
                title="Asymptotic Analysis & Big O Complexity",
                youtube_url="https://www.youtube.com/watch?v=A03oI0znAoc",
                video_id="A03oI0znAoc",
                duration_mins=22,
                channel_name="Gate Smashers",
                description="Time complexity bounds, worst-case scaling, and recursive runtime bounds."
            ),
            # GATE CS - TOC
            VideoMaterial(
                subject="CS",
                topic="Theory of Computation (TOC)",
                subtopic="DFA Construction",
                title="DFA Construction and Minimization",
                youtube_url="https://www.youtube.com/watch?v=58N2N7zJGrY",
                video_id="58N2N7zJGrY",
                duration_mins=25,
                channel_name="Gate Smashers",
                description="Constructing deterministic finite automata for multiple formal languages."
            ),
            # GATE CS - Compiler
            VideoMaterial(
                subject="CS",
                topic="Compiler Design",
                subtopic="Lexical Analysis",
                title="Compiler Design: Parsing & Lexical Analysis",
                youtube_url="https://www.youtube.com/watch?v=8D2Q3fL0sF3",
                video_id="8D2Q3fL0sF3",
                duration_mins=18,
                channel_name="Gate Smashers",
                description="Role of lexical analyzers, tokens extraction, and parser syntax boundaries."
            ),
            # GATE CS - OS
            VideoMaterial(
                subject="CS",
                topic="Operating Systems (OS)",
                subtopic="CPU Scheduling",
                title="CPU Scheduling Algorithms (FCFS, SJF, RR)",
                youtube_url="https://www.youtube.com/watch?v=zFJu8a54_Zc",
                video_id="zFJu8a54_Zc",
                duration_mins=15,
                channel_name="Gate Smashers",
                description="Comparing throughput, waiting times, and preemptive round robin processes."
            ),
            # GATE CS - DBMS
            VideoMaterial(
                subject="CS",
                topic="Databases (DBMS)",
                subtopic="SQL Queries & Joins",
                title="DBMS Joins and Relational Algebra",
                youtube_url="https://www.youtube.com/watch?v=7D3QfE8Hk92",
                video_id="7D3QfE8Hk92",
                duration_mins=24,
                channel_name="Gate Smashers",
                description="Outer joins, inner joins, Cartesian products, and key normalization bounds."
            ),
            # GATE CS - CN
            VideoMaterial(
                subject="CS",
                topic="Computer Networks (CN)",
                subtopic="IP Addressing",
                title="Computer Networks IPv4 Subnetting",
                youtube_url="https://www.youtube.com/watch?v=6D2QfF9Kk01",
                video_id="6D2QfF9Kk01",
                duration_mins=32,
                channel_name="Gate Smashers",
                description="IPv4 classless addressing, CIDR notation, and network mask boundaries."
            ),

            # GATE DA - General Aptitude
            VideoMaterial(
                subject="DA",
                topic="General Aptitude",
                subtopic="Aptitude & Logic",
                title="Quantitative Reasoning & Algebra Tricks",
                youtube_url="https://www.youtube.com/watch?v=A4XyP4S5sBE",
                video_id="A4XyP4S5sBE",
                duration_mins=45,
                channel_name="Gate Smashers",
                description="Algebra shortcuts and logical reasoning mappings."
            ),
            # GATE DA - Linear Algebra
            VideoMaterial(
                subject="DA",
                topic="Linear Algebra",
                subtopic="Matrix Projections",
                title="Strang MIT Linear Algebra: System Solutions",
                youtube_url="https://www.youtube.com/watch?v=ZK3O402wf1c",
                video_id="ZK3O402wf1c",
                duration_mins=39,
                channel_name="MIT OpenCourseWare",
                description="Gilbert Strang details system vector projections and linear spaces."
            ),
            # GATE DA - Calculus
            VideoMaterial(
                subject="DA",
                topic="Calculus and Optimization",
                subtopic="Optimization",
                title="Essence of Calculus (3Blue1Brown)",
                youtube_url="https://www.youtube.com/watch?v=WUvTyaaCl3c",
                video_id="WUvTyaaCl3c",
                duration_mins=16,
                channel_name="3Blue1Brown",
                description="Geometric explanations of limits, slopes, and optimizations."
            ),
            # GATE DA - Probability
            VideoMaterial(
                subject="DA",
                topic="Probability and Statistics",
                subtopic="Bayes Theorem",
                title="Harvard Probability Stat 110: Lecture 1",
                youtube_url="https://www.youtube.com/watch?v=KbB0Fj81ux8",
                video_id="KbB0Fj81ux8",
                duration_mins=48,
                channel_name="Harvard University",
                description="Sample space, probability counting, and conditional events."
            ),
            # GATE DA - Python
            VideoMaterial(
                subject="DA",
                topic="Python Programming and Data Structures",
                subtopic="Python Loops",
                title="Python Programming Basics (freeCodeCamp)",
                youtube_url="https://www.youtube.com/watch?v=rfscVS0vtbw",
                video_id="rfscVS0vtbw",
                duration_mins=55,
                channel_name="freeCodeCamp",
                description="Loops, functions, file handlers, and lists structure in Python."
            ),
            # GATE DA - Algorithms
            VideoMaterial(
                subject="DA",
                topic="Algorithms",
                subtopic="Graph Complexity",
                title="Divide & Conquer Algorithms Complexity",
                youtube_url="https://www.youtube.com/watch?v=A03oI0znAoc",
                video_id="A03oI0znAoc",
                duration_mins=22,
                channel_name="Gate Smashers",
                description="Complexity boundaries of search algorithms, graphs, and matrices scaling."
            ),
            # GATE DA - Database Management
            VideoMaterial(
                subject="DA",
                topic="Database Management and Warehousing",
                subtopic="OLAP Warehouses",
                title="Database Joins & Warehousing Lectures",
                youtube_url="https://www.youtube.com/watch?v=7D3QfE8Hk92",
                video_id="7D3QfE8Hk92",
                duration_mins=24,
                channel_name="Gate Smashers",
                description="SQL grouping queries, normalizations, and star schema structures."
            ),
            # GATE DA - ML
            VideoMaterial(
                subject="DA",
                topic="Machine Learning (ML)",
                subtopic="ML Classifications",
                title="Supervised Learning & Regression (Andrew Ng)",
                youtube_url="https://www.youtube.com/watch?v=KzE_QZ-aPCE",
                video_id="KzE_QZ-aPCE",
                duration_mins=12,
                channel_name="Stanford Online",
                description="Andrew Ng details SVM classifiers, linear models, and optimizations."
            ),
            # GATE DA - AI
            VideoMaterial(
                subject="DA",
                topic="Artificial Intelligence (AI)",
                subtopic="A* Search Heuristics",
                title="UC Berkeley AI CS188: Search Trees",
                youtube_url="https://www.youtube.com/watch?v=8fC_A03sF5E",
                video_id="8fC_A03sF5E",
                duration_mins=34,
                channel_name="UC Berkeley",
                description="Depth First Search, A* heuristic algorithms, and state mapping."
            )
        ]
        db.add_all(videos)
        db.commit()

        # ============================================================
        # 3. SEED FLASHCARDS
        # ============================================================
        print("Seeding Flashcards...")
        flashcards = [
            # Algorithms CS
            Flashcard(
                subject="CS",
                topic="Algorithms",
                front="Master Theorem for Divide & Conquer Recurrences",
                back="For $T(n) = aT(n/b) + f(n)$ where $a \\ge 1, b > 1$:\n1. If $f(n) = O(n^{\\log_b a - \\epsilon})$, then $T(n) = \\Theta(n^{\\log_b a})$\n2. If $f(n) = \\Theta(n^{\\log_b a} \\log^k n)$, then $T(n) = \\Theta(n^{\\log_b a} \\log^{k+1} n)$\n3. If $f(n) = \\Omega(n^{\\log_b a + \\epsilon})$ and regularity condition holds, then $T(n) = \\Theta(f(n))$"
            ),
            # OS CS
            Flashcard(
                subject="CS",
                topic="Operating Systems (OS)",
                front="Turnaround Time & Waiting Time Formulas",
                back="- $\\text{Turnaround Time (TAT)} = \\text{Completion Time (CT)} - \\text{Arrival Time (AT)}$\n- $\\text{Waiting Time (WT)} = \\text{Turnaround Time (TAT)} - \\text{Burst Time (BT)}$"
            ),
            # TOC CS
            Flashcard(
                subject="CS",
                topic="Theory of Computation (TOC)",
                front="Chomsky Hierarchy of Languages",
                back="1. Type 0: Unrestricted Grammar / Recursively Enumerable Language (Turing Machine)\n2. Type 1: Context-Sensitive Grammar / Context-Sensitive Language (Linear Bounded Automaton)\n3. Type 2: Context-Free Grammar / Context-Free Language (Pushdown Automaton)\n4. Type 3: Regular Grammar / Regular Language (Finite Automaton)"
            ),
            # Linear Algebra DA
            Flashcard(
                subject="DA",
                topic="Linear Algebra",
                front="Properties of an Invertible Matrix (Invertible Matrix Theorem)",
                back="For an $n \\times n$ matrix $A$:\n- $A$ is invertible\n- Determinant of $A \\neq 0$\n- $Ax = 0$ has only the trivial solution ($x = 0$)\n- Rank of $A = n$\n- $\\lambda = 0$ is NOT an eigenvalue of $A$"
            ),
            # Probability DA
            Flashcard(
                subject="DA",
                topic="Probability and Statistics",
                front="Bayes' Theorem Formula",
                back="$$P(A|B) = \\frac{P(B|A) P(A)}{P(B)}$$\nWhere $P(A|B)$ is posterior probability, $P(B|A)$ is likelihood, $P(A)$ is prior, and $P(B)$ is marginal probability."
            ),
            # ML DA
            Flashcard(
                subject="DA",
                topic="Machine Learning (ML)",
                front="Bias-Variance Tradeoff definition",
                back="Total Error = $\\text{Bias}^2 + \\text{Variance} + \\text{Irreducible Noise}$.\n- High Bias = Underfitting (simplistic model)\n- High Variance = Overfitting (model captures noise)"
            )
        ]
        db.add_all(flashcards)
        db.commit()

        # ============================================================
        # 4. SEED CURATED QUESTION SETS
        # ============================================================
        print("Seeding Curated Sets...")
        db_questions = db.query(Question).all()
        cs_ids = [q.id for q in db_questions if q.subject == "CS"][:5]
        da_ids = [q.id for q in db_questions if q.subject == "DA"][:5]

        if not cs_ids:
            cs_ids = ["CS_2026_CS-1_Q1", "CS_2026_CS-1_Q2", "CS_2026_CS-1_Q3", "CS_2026_CS-1_Q4", "CS_2026_CS-1_Q5"]
        if not da_ids:
            da_ids = ["DA_2026_DA_Q1", "DA_2026_DA_Q2", "DA_2026_DA_Q3", "DA_2026_DA_Q4", "DA_2026_DA_Q5"]

        curated_sets = [
            CuratedSet(
                name="GATE CS Core Algorithms Essentials",
                description="A handpicked collection of the most important Algorithm questions covering Big O, Sorting, Graphs, and Dynamic Programming.",
                subject="CS",
                questions_csv=",".join(cs_ids)
            ),
            CuratedSet(
                name="Probability and ML Core for DA",
                description="Curated numerical and theoretical questions testing linear algebra, probability, and key machine learning concepts.",
                subject="DA",
                questions_csv=",".join(da_ids)
            )
        ]
        db.add_all(curated_sets)
        db.commit()

        print("All resources successfully seeded in database!")
    except Exception as e:
        db.rollback()
        print(f"Error seeding resources: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    seed_resources()
