import React from 'react';
import Grainient from './Grainient';
import RotatingText from './RotatingText';
import { Target, TrendingUp, Calendar, Zap, LayoutDashboard, Brain, ChevronRight } from 'lucide-react';
import { useApp } from '../context/AppContext';

const LandingPage = () => {
  const { user, setAppMode, setAuthDialog } = useApp();

  return (
    <div className="min-h-screen text-white relative font-sans overflow-x-hidden">
      {/* Background Layer */}
      <div className="fixed inset-0 z-0">
        <Grainient
          color1="#FF9FFC"
          color2="#5227FF"
          color3="#B497CF"
          timeSpeed={0.25}
          colorBalance={0}
          warpStrength={1}
          warpFrequency={5}
          warpSpeed={2}
          warpAmplitude={50}
          blendAngle={0}
          blendSoftness={0.05}
          rotationAmount={500}
          noiseScale={2}
          grainAmount={0.1}
          grainScale={2}
          grainAnimated={false}
          contrast={1.5}
          gamma={1}
          saturation={1}
          centerX={0}
          centerY={0}
          zoom={0.9}
        />
        <div className="absolute inset-0 bg-black/40 backdrop-blur-[2px]"></div>
      </div>

      {/* Content Layer */}
      <div className="relative z-10">
        {/* Navigation */}
        <nav className="flex items-center justify-between px-8 py-6 max-w-7xl mx-auto">
          <div className="text-2xl font-bold tracking-tighter flex items-center gap-2">
            <span className="bg-gradient-to-r from-purple-400 to-pink-400 bg-clip-text text-transparent">AstraPath</span>
          </div>
          <button
            onClick={() => user ? setAppMode(user.role) : setAuthDialog('login')}
            className="px-6 py-2 rounded-full bg-white/10 hover:bg-white/20 border border-white/20 backdrop-blur-md transition-all text-sm font-medium"
          >
            {user ? 'Open Portal' : 'Sign In'}
          </button>
        </nav>

        {/* Hero Section */}
        <main className="max-w-7xl mx-auto px-8 pt-20 pb-32 flex flex-col items-center text-center">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-white/5 border border-white/10 backdrop-blur-md mb-8">
            <span className="w-2 h-2 rounded-full bg-green-400 animate-pulse"></span>
            <span className="text-sm font-medium text-gray-300">Agentic Goal Platform MVP</span>
          </div>
          
          <h1 className="text-5xl md:text-7xl font-extrabold tracking-tight mb-8 leading-tight">
            Achieve more with <br />
            <RotatingText
              texts={['Intelligent Planning', 'Evidence-Based Learning', 'Adaptive Recovery', 'Constraint-Aware Goals', 'Mastery-Based Progress']}
              mainClassName="px-4 sm:px-4 md:px-5 bg-purple-500/20 text-purple-200 border border-purple-500/30 overflow-hidden py-1 sm:py-2 md:py-3 justify-center rounded-2xl mt-4 inline-flex backdrop-blur-md shadow-[0_0_40px_-10px_rgba(168,85,247,0.4)]"
              staggerFrom="last"
              initial={{ y: "100%" }}
              animate={{ y: 0 }}
              exit={{ y: "-120%" }}
              staggerDuration={0.025}
              splitLevelClassName="overflow-hidden pb-1 sm:pb-2 md:pb-2"
              transition={{ type: "spring", damping: 30, stiffness: 400 }}
              rotationInterval={3500}
              splitBy="characters"
              auto
              loop
            />
          </h1>
          
          <p className="max-w-2xl text-lg md:text-xl text-gray-300 mb-12 font-medium leading-relaxed">
            Transform student planning from a static timetable into an evidence-driven, personalized, and mentor-aware achievement system. Say goodbye to vague roadmaps.
          </p>
          
          <div className="flex items-center gap-4 flex-col sm:flex-row">
            <button
              onClick={() => user ? setAppMode(user.role) : setAuthDialog('register')}
              className="px-8 py-4 rounded-full bg-white text-black font-bold text-lg hover:scale-105 transition-transform flex items-center gap-2 shadow-xl shadow-white/10"
            >
              {user ? 'Open Your Portal' : 'Start Your Journey'} <ChevronRight className="w-5 h-5" />
            </button>
            <button
              onClick={() => document.getElementById('capabilities')?.scrollIntoView({ behavior: 'smooth' })}
              className="px-8 py-4 rounded-full bg-black/40 border border-white/20 text-white font-bold text-lg hover:bg-black/60 transition-colors backdrop-blur-md"
            >
              Explore Capabilities
            </button>
          </div>
        </main>

        {/* Deliverables & Features */}
        <section id="capabilities" className="bg-black/80 backdrop-blur-xl border-t border-white/10 py-32">
          <div className="max-w-7xl mx-auto px-8">
            <div className="text-center mb-20">
              <h2 className="text-3xl md:text-5xl font-bold mb-6">The AstraPath Ideology</h2>
              <p className="text-gray-400 max-w-2xl mx-auto text-lg">
                We believe students struggle not because they lack ambition, but because generic roadmaps fail them. AstraPath connects goal feasibility, planning, evidence, mastery, and adaptive recovery.
              </p>
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
              <FeatureCard 
                icon={<Target className="w-8 h-8 text-pink-400" />}
                title="Goal-to-Evidence Planning"
                description="Goals are decomposed into outcomes, competencies, and milestones. Progress requires proof, not just checking a box."
              />
              <FeatureCard 
                icon={<LayoutDashboard className="w-8 h-8 text-purple-400" />}
                title="Dynamic Goal Graph"
                description="Your plan is a living graph. Dependencies recalculate instantly when your goal, deadline, or profile changes."
              />
              <FeatureCard 
                icon={<TrendingUp className="w-8 h-8 text-indigo-400" />}
                title="Mastery-Based Progress"
                description="Progress is driven by quiz performance, project evidence, mentor feedback, and confidence calibration."
              />
              <FeatureCard 
                icon={<Brain className="w-8 h-8 text-blue-400" />}
                title="Adaptive Recovery"
                description="Falling behind? AstraPath identifies why and generates a recovery plan instead of punishing you with overdue tasks."
              />
              <FeatureCard 
                icon={<Calendar className="w-8 h-8 text-cyan-400" />}
                title="Constraint-Aware Scheduling"
                description="We factor in your classes, internships, sleep preferences, and high-focus hours to build a realistic timeline."
              />
              <FeatureCard 
                icon={<Zap className="w-8 h-8 text-fuchsia-400" />}
                title="Evidence Portfolio"
                description="Build a verifiable portfolio of mini-projects, commits, and certificates while you learn to prove your capability."
              />
            </div>
          </div>
        </section>

        {/* Footer */}
        <footer className="bg-black py-12 border-t border-white/10 text-center text-gray-500">
          <div className="flex items-center justify-center gap-2 mb-4">
            <span className="w-4 h-4 bg-purple-500 rounded-sm rotate-45"></span>
            <span className="font-bold text-white tracking-widest">ASTRAPATH</span>
          </div>
          <p>© 2026 AstraPath. Agentic Student Goal Planning.</p>
        </footer>
      </div>
    </div>
  );
};

const FeatureCard = ({ icon, title, description }) => (
  <div className="p-8 rounded-3xl bg-white/5 border border-white/10 hover:bg-white/10 hover:-translate-y-2 transition-all duration-300 group">
    <div className="w-16 h-16 rounded-2xl bg-white/5 border border-white/10 flex items-center justify-center mb-6 group-hover:scale-110 transition-transform">
      {icon}
    </div>
    <h3 className="text-xl font-bold mb-3 text-gray-100">{title}</h3>
    <p className="text-gray-400 leading-relaxed">
      {description}
    </p>
  </div>
);

export default LandingPage;
