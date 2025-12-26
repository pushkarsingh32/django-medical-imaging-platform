import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Target, Eye, Award, Users, Heart, Zap } from 'lucide-react';

export default function AboutPage() {
  const values = [
    {
      icon: Heart,
      title: 'Patient-Centric',
      description: 'We prioritize patient care and data security in everything we build.',
    },
    {
      icon: Zap,
      title: 'Innovation',
      description: 'Continuously improving our platform with cutting-edge technology.',
    },
    {
      icon: Users,
      title: 'Collaboration',
      description: 'Enabling seamless teamwork between healthcare professionals.',
    },
    {
      icon: Award,
      title: 'Excellence',
      description: 'Committed to delivering the highest quality medical imaging solutions.',
    },
  ];

  const team = [
    {
      role: 'Medical Director',
      description: 'Leading our clinical strategy and ensuring medical accuracy.',
    },
    {
      role: 'Chief Technology Officer',
      description: 'Driving innovation in medical imaging technology.',
    },
    {
      role: 'Head of Product',
      description: 'Designing intuitive solutions for healthcare professionals.',
    },
    {
      role: 'Security Lead',
      description: 'Ensuring HIPAA compliance and data protection.',
    },
  ];

  return (
    <div className="flex flex-col">
      {/* Hero Section */}
      <section className="bg-gradient-to-br from-blue-50 via-white to-purple-50 py-20">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center space-y-6">
          <h1 className="text-4xl md:text-5xl font-bold text-gray-900">
            About MediScan
          </h1>
          <p className="text-xl text-gray-600 leading-relaxed">
            Revolutionizing medical imaging with innovative technology that empowers
            healthcare professionals to deliver better patient care.
          </p>
        </div>
      </section>

      {/* Mission & Vision */}
      <section className="py-20 bg-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-12">
            <Card className="border-2">
              <CardHeader>
                <div className="h-12 w-12 rounded-lg bg-primary/10 flex items-center justify-center mb-4">
                  <Target className="h-6 w-6 text-primary" />
                </div>
                <CardTitle className="text-2xl">Our Mission</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-gray-600 leading-relaxed">
                  To transform healthcare delivery by providing innovative medical imaging
                  solutions that improve diagnostic accuracy, streamline workflows, and
                  enhance patient outcomes. We're committed to making advanced imaging
                  technology accessible to healthcare facilities of all sizes.
                </p>
              </CardContent>
            </Card>

            <Card className="border-2">
              <CardHeader>
                <div className="h-12 w-12 rounded-lg bg-primary/10 flex items-center justify-center mb-4">
                  <Eye className="h-6 w-6 text-primary" />
                </div>
                <CardTitle className="text-2xl">Our Vision</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-gray-600 leading-relaxed">
                  To become the world's most trusted medical imaging platform, setting new
                  standards for quality, security, and innovation in healthcare technology.
                  We envision a future where every healthcare provider has access to
                  enterprise-grade diagnostic tools.
                </p>
              </CardContent>
            </Card>
          </div>
        </div>
      </section>

      {/* Our Story */}
      <section className="py-20 bg-gray-50">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center space-y-4 mb-12">
            <h2 className="text-3xl md:text-4xl font-bold text-gray-900">Our Story</h2>
          </div>
          <div className="prose prose-lg max-w-none">
            <p className="text-gray-600 leading-relaxed mb-6">
              Founded in 2020, MediScan emerged from a simple observation: healthcare
              professionals needed better tools to manage and analyze medical images.
              Our founding team of radiologists, software engineers, and healthcare
              administrators came together with a shared vision of creating a platform
              that truly understands the needs of modern medical facilities.
            </p>
            <p className="text-gray-600 leading-relaxed mb-6">
              Starting with a small pilot program at three hospitals, we've grown to
              serve over 500 healthcare facilities worldwide. Our platform now processes
              millions of medical images annually, helping doctors make faster, more
              accurate diagnoses and ultimately saving lives.
            </p>
            <p className="text-gray-600 leading-relaxed">
              Today, MediScan continues to innovate, introducing new features and
              capabilities based on direct feedback from our users. We're proud to be
              trusted by leading medical institutions and remain committed to our mission
              of improving healthcare through technology.
            </p>
          </div>
        </div>
      </section>

      {/* Core Values */}
      <section className="py-20 bg-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center space-y-4 mb-16">
            <h2 className="text-3xl md:text-4xl font-bold text-gray-900">
              Our Core Values
            </h2>
            <p className="text-lg text-gray-600 max-w-2xl mx-auto">
              The principles that guide everything we do
            </p>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8">
            {values.map((value, index) => {
              const Icon = value.icon;
              return (
                <Card key={index} className="border-2 text-center">
                  <CardHeader>
                    <div className="h-16 w-16 rounded-full bg-primary/10 flex items-center justify-center mx-auto mb-4">
                      <Icon className="h-8 w-8 text-primary" />
                    </div>
                    <CardTitle className="text-xl">{value.title}</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <p className="text-gray-600">{value.description}</p>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        </div>
      </section>

      {/* Leadership Team */}
      <section className="py-20 bg-gray-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center space-y-4 mb-16">
            <h2 className="text-3xl md:text-4xl font-bold text-gray-900">
              Leadership Team
            </h2>
            <p className="text-lg text-gray-600 max-w-2xl mx-auto">
              Experienced professionals dedicated to advancing healthcare technology
            </p>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8">
            {team.map((member, index) => (
              <Card key={index}>
                <CardHeader>
                  <div className="h-32 w-32 rounded-full bg-gradient-to-br from-primary/20 to-purple-500/20 mx-auto mb-4"></div>
                  <CardTitle className="text-lg text-center">{member.role}</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-gray-600 text-center">
                    {member.description}
                  </p>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      </section>

      {/* Stats */}
      <section className="py-20 bg-gradient-to-r from-primary to-purple-600">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-8 text-center">
            <div>
              <p className="text-4xl md:text-5xl font-bold text-white mb-2">500+</p>
              <p className="text-white/90">Healthcare Facilities</p>
            </div>
            <div>
              <p className="text-4xl md:text-5xl font-bold text-white mb-2">50M+</p>
              <p className="text-white/90">Images Processed</p>
            </div>
            <div>
              <p className="text-4xl md:text-5xl font-bold text-white mb-2">10K+</p>
              <p className="text-white/90">Medical Professionals</p>
            </div>
            <div>
              <p className="text-4xl md:text-5xl font-bold text-white mb-2">99.9%</p>
              <p className="text-white/90">Uptime Guarantee</p>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
