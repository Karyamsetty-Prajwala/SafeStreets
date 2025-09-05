// components/About.jsx
import React from 'react';

export default function About() {
  return (
    <section className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 to-white px-6 py-12">
      <div className="w-full max-w-4xl bg-white p-10 rounded-2xl shadow-2xl border border-blue-200">
        <h1 className="text-4xl font-bold text-blue-800 mb-6 text-center">About SafeStreets</h1>

        <p className="text-gray-700 text-lg leading-relaxed mb-6">
          SafeStreets is a cutting-edge web application designed to empower urban travelers with data-driven safety intelligence.
          Our mission is to shift the paradigm of navigation from merely efficient to proactively safe, providing users with the tools
          they need to make informed decisions about their travel, thereby enhancing their peace of mind and overall security.
        </p>

        <p className="text-gray-700 text-lg leading-relaxed mb-6">
          By leveraging machine learning and real-time data, SafeStreets helps you find the safest route to your destination, offering
          peace of mind every step of the way.
        </p>

        <h2 className="text-2xl font-semibold text-blue-700 mb-4">Key Features:</h2>
        <ul className="list-disc list-inside text-gray-800 space-y-2 text-lg">
          <li>
            <strong>Predictive Safety Scores:</strong> Our unique ML model analyzes historical crime data to provide a dynamic safety score for each route.
          </li>
          <li>
            <strong>Safety-Optimized Routes:</strong> We offer alternative routes that are optimized for safety, helping you avoid high-risk areas.
          </li>
          <li>
            <strong>Emergency Support:</strong> A quick-access panel provides essential public and personal emergency contact numbers.
          </li>
        </ul>
      </div>
    </section>
  );
}
